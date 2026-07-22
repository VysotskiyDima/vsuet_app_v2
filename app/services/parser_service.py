"""ParserService — взаимодействие с rating.vsuet.ru.

Каркас обхода ASP.NET WebForms взят из приложенного parser.py: скрытые поля
(__VIEWSTATE и пр.), POST через __EVENTTARGET, конкурентный обход факультетов →
групп → ведомостей под общим семафором, ретраи при сетевых ошибках и 429,
кодировка windows-1251. Год/семестр берутся из настроек (env).

ВНИМАНИЕ по лимитам: CONCURRENCY и параметры ретраев подобраны как безопасный
предел для слабого сервера ВГУИТ — повышать нельзя.
"""

import asyncio
import random
import re

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.logging_utils import get_logger
from app.parser.html_parser import parse_ved_html




log = get_logger(__name__)




# Тюнинг и его обоснование живут в config.ScraperSettings — здесь только производные.
_SCRAPER = settings.scraper
TIMEOUT = httpx.Timeout(_SCRAPER.timeout_s)
CONCURRENCY = _SCRAPER.concurrency
RETRIES = _SCRAPER.retries
RETRY_BACKOFF = _SCRAPER.retry_backoff_s
RETRY_MAX_DELAY = _SCRAPER.retry_max_delay_s

LIMITS = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
HEADERS = {"User-Agent": _SCRAPER.user_agent, "Referer": settings.site.base_url}

_FAC_SELECT = "ctl00$ContentPage$cmbFacultets"
_GROUP_SELECT = "ctl00$ContentPage$cmbGroups"


def _backoff_delay(attempt: int) -> float:
    """Экспоненциальный бэкофф с полным джиттером.

    Запросы, упавшие по таймауту одной волной (слабый сервер отдаёт их пачкой),
    без джиттера ретраятся синхронно и снова перегружают сервер. Случайная
    задержка из [0, base] размазывает повторы во времени.
    """
    base = min(RETRY_BACKOFF * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
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
    return [
        {"id": o["value"], "name": o.text.strip()}
        for o in select.find_all("option")
        if o.get("value")
    ]


def _parse_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": re.compile(r"Grid")})
    if not table:
        return []
    urls = []
    for a in table.find_all("a", href=True):
        m = re.search(r"id=(\d+)", a["href"])
        if m:
            urls.append(f"{settings.site.ved_url}?id={m.group(1)}")
    return urls




class ParserService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(CONCURRENCY)
        self._ved_pool: asyncio.Queue[httpx.AsyncClient] = asyncio.Queue()

    async def __aenter__(self) -> "ParserService":
        self._client = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, limits=LIMITS, timeout=TIMEOUT)
        for _ in range(CONCURRENCY):
            self._ved_pool.put_nowait(
                httpx.AsyncClient(
                    headers=HEADERS,
                    follow_redirects=True,
                    limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                    timeout=TIMEOUT,
                )
            )
        log.debug(
            "HTTP clients opened",
            ved_pool=CONCURRENCY, concurrency=CONCURRENCY,
            connect_s=TIMEOUT.connect, read_s=TIMEOUT.read, retries=RETRIES,
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
        kwargs.setdefault("timeout", TIMEOUT)
        http = client if client is not None else self.client
        for attempt in range(1, RETRIES + 1):
            try:
                r = await http.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                if attempt == RETRIES:
                    log.error("Request failed", method=method, url=url, attempts=RETRIES, error=repr(exc))
                    raise
                delay = _backoff_delay(attempt)
                log.warning(
                    "Request retry",
                    method=method, url=url, attempt=f"{attempt}/{RETRIES}",
                    error=repr(exc), delay_s=round(delay, 1),
                )
                await asyncio.sleep(delay)
                continue

            if r.status_code == 429:
                if attempt == RETRIES:
                    log.warning("429 retry limit exceeded", url=url)
                    return r
                retry_after = r.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after is not None else _backoff_delay(attempt)
                except ValueError:
                    delay = _backoff_delay(attempt)
                log.warning("429 received", url=url, attempt=f"{attempt}/{RETRIES}", delay_s=round(delay, 1))
                await asyncio.sleep(delay)
                continue

            return r
        raise RuntimeError("unreachable")

    async def _post(self, data: dict) -> str:
        r = await self._request("POST", settings.site.base_url, data=data)
        r.encoding = "windows-1251"
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
                html = await self._post(
                    {
                        "__EVENTTARGET": _GROUP_SELECT,
                        "__EVENTARGUMENT": "",
                        **fac_fields,
                        _FAC_SELECT: fac["id"],
                        _GROUP_SELECT: grp["id"],
                        "ctl00$ContentPage$cmbYears": settings.parsing.year,
                        "ctl00$ContentPage$cmbSem": settings.parsing.semester,
                    }
                )
            urls = await asyncio.to_thread(_parse_urls, html)
            log.debug("Group vedomosts collected", group=grp["name"], count=len(urls))
            return urls
        except Exception as exc:
            log.error("Error collecting group vedomosts", group=grp["name"], error=repr(exc))
            return []


    async def _faculty_groups(self, base_fields: dict, fac: dict) -> dict[str, list[str]]:
        async with self._sem:
            fac_html = await self._post(
                {
                    "__EVENTTARGET": _FAC_SELECT,
                    "__EVENTARGUMENT": "",
                    **base_fields,
                    _FAC_SELECT: fac["id"],
                    _GROUP_SELECT: "",
                    "ctl00$ContentPage$cmbYears": settings.parsing.year,
                    "ctl00$ContentPage$cmbSem": settings.parsing.semester,
                }
            )
        fac_fields = await asyncio.to_thread(_parse_viewstate, fac_html)
        groups = await asyncio.to_thread(_parse_select, fac_html, _GROUP_SELECT)
        log.debug("Faculty groups collected", faculty=fac["name"], count=len(groups))

        lists = await asyncio.gather(
            *(self._group_urls(fac_fields, fac, grp) for grp in groups)
        )
        return {grp["name"]: urls for grp, urls in zip(groups, lists)}


    async def collect_ved_links(self) -> dict[str, list[str]]:
        """Конкурентно собирает ссылки на ведомости по всем группам.

        Возвращает {название_группы: [url1, url2, ...]}.
        """
        r = await self._request("GET", settings.site.base_url)
        r.encoding = "windows-1251"
        base_fields = await asyncio.to_thread(_parse_viewstate, r.text)
        faculties = await asyncio.to_thread(_parse_select, r.text, _FAC_SELECT)
        log.debug("Start collecting links", faculties=len(faculties))

        per_faculty = await asyncio.gather(
            *(self._faculty_groups(base_fields, fac) for fac in faculties)
        )

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
        r.encoding = "windows-1251"
        # bs4-разбор — CPU-bound; в потоке, чтобы не блокировать event loop
        # (в нём же живёт FastAPI: синхронный разбор подвешивал API на время цикла).
        records = await asyncio.to_thread(parse_ved_html, r.text)
        log.debug("Vedomost parsed", records=len(records), url=url)
        return records
