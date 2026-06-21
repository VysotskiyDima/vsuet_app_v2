"""ParserService — взаимодействие с rating.vsuet.ru.

Каркас обхода ASP.NET WebForms взят из приложенного parser.py: скрытые поля
(__VIEWSTATE и пр.), POST через __EVENTTARGET, конкурентный обход факультетов →
групп → ведомостей под общим семафором, ретраи при сетевых ошибках и 429,
кодировка windows-1251. Год/семестр берутся из настроек (env).

ВНИМАНИЕ по лимитам: CONCURRENCY и параметры ретраев подобраны как безопасный
предел для слабого сервера ВГУИТ — повышать нельзя.
"""

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.parser.html_parser import parse_ved_html




logger = logging.getLogger(__name__)




BASE_URL = "https://rating.vsuet.ru/web/ved/Default.aspx"
VED_URL = "https://rating.vsuet.ru/web/ved/Ved.aspx"

TIMEOUT = 30
CONCURRENCY = 18      # одновременных запросов — главный рычаг скорости, не повышать
RETRIES = 3
RETRY_BACKOFF = 2

LIMITS = httpx.Limits(max_connections=CONCURRENCY, max_keepalive_connections=CONCURRENCY)
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": BASE_URL}

_FAC_SELECT = "ctl00$ContentPage$cmbFacultets"
_GROUP_SELECT = "ctl00$ContentPage$cmbGroups"




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
            urls.append(f"{VED_URL}?id={m.group(1)}")
    return urls




class ParserService:
    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._sem = asyncio.Semaphore(CONCURRENCY)

    async def __aenter__(self) -> "ParserService":
        self._client = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, limits=LIMITS)
        logger.debug("HTTP client opened  |  concurrency=%d  timeout=%ds  retries=%d", CONCURRENCY, TIMEOUT, RETRIES)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("HTTP client closed")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ParserService используется вне async-контекста")
        return self._client

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        kwargs.setdefault("timeout", TIMEOUT)
        for attempt in range(1, RETRIES + 1):
            try:
                r = await self.client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                if attempt == RETRIES:
                    logger.error("Request %s %s failed after %d attempts: %s", method, url, RETRIES, exc)
                    raise
                logger.warning(
                    "%s %s  attempt %d/%d  error: %s", method, url, attempt, RETRIES, exc
                )
                await asyncio.sleep(RETRY_BACKOFF * attempt)
                continue

            if r.status_code == 429:
                if attempt == RETRIES:
                    logger.warning("429 %s — retry limit exceeded", url)
                    return r
                try:
                    delay = float(r.headers.get("Retry-After", RETRY_BACKOFF * attempt))
                except ValueError:
                    delay = RETRY_BACKOFF * attempt
                logger.warning(
                    "429 %s  attempt %d/%d  delay %.1fs", url, attempt, RETRIES, delay
                )
                await asyncio.sleep(delay)
                continue

            return r
        raise RuntimeError("unreachable")

    async def _post(self, data: dict) -> str:
        r = await self._request("POST", BASE_URL, data=data)
        r.encoding = "windows-1251"
        return r.text

    # --- публичные методы ---

    async def check_site_availability(self) -> bool:
        """True, если сайт отвечает HTTP 200."""
        try:
            r = await self._request("GET", BASE_URL)
        except httpx.HTTPError:
            logger.warning("Site is unavailable (network error)")
            return False
        available = r.status_code == 200
        if available:
            logger.debug("Site is available (HTTP %d)", r.status_code)
        else:
            logger.warning("Site returned HTTP %d", r.status_code)
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
                        "ctl00$ContentPage$cmbYears": settings.parsing_year,
                        "ctl00$ContentPage$cmbSem": settings.parsing_semester,
                    }
                )
            urls = _parse_urls(html)
            logger.debug("Group %s -> %d vedomosts", grp["name"], len(urls))
            return urls
        except Exception as exc:
            logger.error("Error collecting vedomosts for group %s: %s", grp["name"], exc)
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
                    "ctl00$ContentPage$cmbYears": settings.parsing_year,
                    "ctl00$ContentPage$cmbSem": settings.parsing_semester,
                }
            )
        fac_fields = _parse_viewstate(fac_html)
        groups = _parse_select(fac_html, _GROUP_SELECT)
        logger.debug("Faculty %s -> %d groups", fac["name"], len(groups))

        lists = await asyncio.gather(
            *(self._group_urls(fac_fields, fac, grp) for grp in groups)
        )
        return {grp["name"]: urls for grp, urls in zip(groups, lists)}


    async def collect_ved_links(self) -> dict[str, list[str]]:
        """Конкурентно собирает ссылки на ведомости по всем группам.

        Возвращает {название_группы: [url1, url2, ...]}.
        """
        r = await self._request("GET", BASE_URL)
        r.encoding = "windows-1251"
        base_fields = _parse_viewstate(r.text)
        faculties = _parse_select(r.text, _FAC_SELECT)
        logger.debug("Start collecting links  |  faculties: %d", len(faculties))

        per_faculty = await asyncio.gather(
            *(self._faculty_groups(base_fields, fac) for fac in faculties)
        )

        result: dict[str, list[str]] = {}
        for mapping in per_faculty:
            for group_name, urls in mapping.items():
                result.setdefault(group_name, []).extend(urls)

        total_urls = sum(len(v) for v in result.values())
        logger.debug(
            "Link collection completed  |  groups: %d  vedomosts: %d", len(result), total_urls
        )
        return result


    async def parse_ved(self, url: str) -> list[dict]:
        """Скачивает и парсит одну ведомость в записи целевого формата.

        Нерабочие ведомости (HTTP != 200 или нет ucVedBox_lblTypeVed) дают
        пустой список и не прерывают цикл.
        """
        try:
            r = await self._request("GET", url)
        except httpx.HTTPError as exc:
            logger.warning("Failed to download vedomost %s: %s", url, exc)
            return []
        # Ранний признак нерабочей ведомости — статус 500 (и любой не-200).
        if r.status_code != 200:
            logger.debug("Non-functional vedomost (HTTP %d): %s", r.status_code, url)
            return []
        r.encoding = "windows-1251"
        records = parse_ved_html(r.text)
        logger.debug("Parsed %d records from %s", len(records), url)
        return records
