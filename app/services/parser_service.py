"""ParserService — взаимодействие с rating.vsuet.ru.

Каркас обхода ASP.NET WebForms: скрытые поля (__VIEWSTATE и пр.), POST через
__EVENTTARGET, конкурентный обход факультетов → групп → ведомостей под общим
семафором, ретраи при сетевых ошибках и 429. Весь тюнинг (конкурентность,
таймауты, ретраи) и разметка сайта — в config: ScraperSettings, HtmlFormSettings,
RatingSiteSettings; здесь только логика обхода.
"""

import asyncio
import random
import re

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.logging_config import get_logger
from app.parser.html_parser import parse_ved_html

log = get_logger(__name__)


def _backoff_delay(attempt: int) -> float:
    """Экспоненциальный бэкофф с полным джиттером.

    Запросы, упавшие по таймауту одной волной (слабый сервер отдаёт их пачкой),
    без джиттера ретраятся синхронно и снова перегружают сервер. Случайная
    задержка из [0, base] размазывает повторы во времени.
    """
    cfg = settings.scraper
    base = min(cfg.retry_backoff_s * (2 ** (attempt - 1)), cfg.retry_max_delay_s)
    return random.uniform(0, base)


def _parse_viewstate(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    fields = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        tag = soup.find("input", {"name": name})
        if tag:
            fields[name] = tag.get("value", "")
    return fields


def _parse_select(html: str, name: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    select = soup.find("select", {"name": name})
    if not select:
        return []
    return [{"id": o["value"], "name": o.text.strip()} for o in select.find_all("option") if o.get("value")]


def _parse_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": re.compile(settings.html_form.grid_id_pattern)})
    if not table:
        return []
    urls = []
    for a in table.find_all("a", href=True):
        m = re.search(r"id=(\d+)", a["href"])
        if m:
            urls.append(f"{settings.site.ved_url}?id={m.group(1)}")
    return urls


def _form_data(event_target: str, viewstate: dict, fac_id: str, group_id: str) -> dict:
    """POST-форма Default.aspx: событие + viewstate + текущие значения селектов."""
    form = settings.html_form
    return {
        "__EVENTTARGET": event_target,
        "__EVENTARGUMENT": "",
        **viewstate,
        form.faculty_select: fac_id,
        form.group_select: group_id,
        form.years_select: settings.parsing.year,
        form.semester_select: settings.parsing.semester,
    }


class ParserService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(settings.scraper.concurrency)
        # Пул клиентов для скачивания ведомостей. ASP.NET сериализует запросы
        # ОДНОЙ сессии (lock на ASP.NET_SessionId): через общий клиент
        # «конкурентные» GET выполняются сервером по одному. Отдельный клиент =
        # отдельная сессия; клиент выдаётся ровно одной корутине за раз, поэтому
        # внутри сессии конкуренции нет, а между сессиями сервер параллелит.
        self._ved_pool: asyncio.Queue[httpx.AsyncClient] = asyncio.Queue()

    async def __aenter__(self) -> "ParserService":
        cfg = settings.scraper
        timeout = httpx.Timeout(cfg.timeout_s)
        headers = {"User-Agent": cfg.user_agent, "Referer": settings.site.base_url}
        self._client = httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=cfg.concurrency, max_keepalive_connections=cfg.concurrency),
            timeout=timeout,
        )
        for _ in range(cfg.concurrency):
            self._ved_pool.put_nowait(
                httpx.AsyncClient(
                    headers=headers,
                    follow_redirects=True,
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                    timeout=timeout,
                )
            )
        log.debug(
            "HTTP clients opened",
            ved_pool=cfg.concurrency,
            concurrency=cfg.concurrency,
            timeout_s=cfg.timeout_s,
            retries=cfg.retries,
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        while not self._ved_pool.empty():
            await self._ved_pool.get_nowait().aclose()
        log.debug("HTTP clients closed")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ParserService используется вне async-контекста")
        return self._client

    async def _request(
        self, method: str, url: str, client: httpx.AsyncClient | None = None, **kwargs
    ) -> httpx.Response:
        retries = settings.scraper.retries
        http = client if client is not None else self.client
        for attempt in range(1, retries + 1):
            try:
                r = await http.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                if attempt == retries:
                    log.error("Request failed", method=method, url=url, attempts=retries, error=repr(exc))
                    raise
                delay = _backoff_delay(attempt)
                log.warning(
                    "Request retry",
                    method=method,
                    url=url,
                    attempt=f"{attempt}/{retries}",
                    error=repr(exc),
                    delay_s=round(delay, 1),
                )
                await asyncio.sleep(delay)
                continue

            if r.status_code == 429:
                if attempt == retries:
                    log.warning("429 retry limit exceeded", url=url)
                    return r
                retry_after = r.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after is not None else _backoff_delay(attempt)
                except ValueError:
                    delay = _backoff_delay(attempt)
                log.warning("429 received", url=url, attempt=f"{attempt}/{retries}", delay_s=round(delay, 1))
                await asyncio.sleep(delay)
                continue

            return r
        raise RuntimeError("unreachable")

    async def _post(self, data: dict) -> str:
        r = await self._request("POST", settings.site.base_url, data=data)
        r.encoding = settings.site.encoding
        return r.text

    # --- публичные методы ---

    async def check_site_availability(self) -> bool:
        """True, если сайт отвечает HTTP 200."""
        try:
            r = await self._request("GET", settings.site.base_url)
        except httpx.HTTPError:
            log.warning("Site is unavailable (network error)")
            return False
        available = r.status_code == 200
        if available:
            log.debug("Site is available", status=r.status_code)
        else:
            log.warning("Site is unavailable", status=r.status_code)
        return available

    async def _group_urls(self, fac_fields: dict, fac: dict, grp: dict) -> list[str]:
        try:
            async with self._sem:
                html = await self._post(_form_data(settings.html_form.group_select, fac_fields, fac["id"], grp["id"]))
            urls = await asyncio.to_thread(_parse_urls, html)
            log.debug("Group vedomosts collected", group=grp["name"], count=len(urls))
            return urls
        except Exception as exc:
            log.error("Error collecting group vedomosts", group=grp["name"], error=repr(exc))
            return []

    async def _faculty_groups(self, base_fields: dict, fac: dict) -> dict[str, list[str]]:
        async with self._sem:
            fac_html = await self._post(_form_data(settings.html_form.faculty_select, base_fields, fac["id"], ""))
        fac_fields = await asyncio.to_thread(_parse_viewstate, fac_html)
        groups = await asyncio.to_thread(_parse_select, fac_html, settings.html_form.group_select)
        log.debug("Faculty groups collected", faculty=fac["name"], count=len(groups))

        lists = await asyncio.gather(*(self._group_urls(fac_fields, fac, grp) for grp in groups))
        return {grp["name"]: urls for grp, urls in zip(groups, lists, strict=True)}

    async def collect_ved_links(self) -> dict[str, list[str]]:
        """Конкурентно собирает ссылки на ведомости по всем группам.

        Возвращает {название_группы: [url1, url2, ...]}.
        """
        r = await self._request("GET", settings.site.base_url)
        r.encoding = settings.site.encoding
        base_fields = await asyncio.to_thread(_parse_viewstate, r.text)
        faculties = await asyncio.to_thread(_parse_select, r.text, settings.html_form.faculty_select)
        log.debug("Start collecting links", faculties=len(faculties))

        per_faculty = await asyncio.gather(*(self._faculty_groups(base_fields, fac) for fac in faculties))

        result: dict[str, list[str]] = {}
        for mapping in per_faculty:
            for group_name, urls in mapping.items():
                result.setdefault(group_name, []).extend(urls)

        total_urls = sum(len(v) for v in result.values())
        log.debug("Link collection completed", groups=len(result), vedomosts=total_urls)
        return result

    async def parse_ved(self, url: str) -> list[dict] | None:
        """Скачивает и парсит одну ведомость в записи целевого формата.

        Различаем два исхода с пустым результатом:
          * None  — ведомость **потеряна** (сетевая ошибка или 429 после всех
            ретраев); это и есть реальная потеря для метрики.
          * []    — ведомость нерабочая/пустая (HTTP != 200, нет маркера типа
            или в ней нет записей); это штатный пропуск, не потеря.
        """
        client = await self._ved_pool.get()
        try:
            r = await self._request("GET", url, client=client)
        except httpx.HTTPError as exc:
            log.warning("Failed to download vedomost", url=url, error=repr(exc))
            return None
        finally:
            self._ved_pool.put_nowait(client)
        # 429 после исчерпания ретраев — реальная потеря.
        if r.status_code == 429:
            log.warning("Vedomost lost after retries (HTTP 429)", url=url)
            return None
        # Ранний признак нерабочей ведомости — статус 500 (и любой иной не-200).
        if r.status_code != 200:
            log.debug("Non-functional vedomost", status=r.status_code, url=url)
            return []
        r.encoding = settings.site.encoding
        # bs4-разбор — CPU-bound; в потоке, чтобы не блокировать event loop
        # (в нём же живёт FastAPI: синхронный разбор подвешивал API на время цикла).
        records = await asyncio.to_thread(parse_ved_html, r.text)
        log.debug("Vedomost parsed", records=len(records), url=url)
        return records
