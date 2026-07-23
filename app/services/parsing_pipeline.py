"""Пайплайн полного цикла парсинга: пять этапов от проверки сайта до swap БД.

Вынесен из app/scheduler/jobs.py: планировщик только триггерит запуск по
расписанию, а вся логика цикла и его метрики живут здесь. Зависимостями
(ParserService, RedisRepository) владеет вызывающий — пайплайн не открывает
и не закрывает ресурсы, поэтому легко тестируется на подменах.

Этапы: 1) доступность сайта, 2) очистка фоновой БД, 3) сбор ссылок,
4) парсинг и запись, 5) переключение активной БД.

Почему очистка фоновой БД — отдельный этап ПЕРЕД записью, а не в конце: это
страховка «на всякий случай». Она гарантирует чистую цель записи независимо от
того, чем закончился предыдущий цикл — включая жёсткое убийство процесса
(SIGKILL/OOM/сбой питания), которое пропускает любую очистку в конце. Если бы
чистили только в конце, оборвавшийся цикл оставил бы частичные данные, к которым
следующий цикл дописал бы новые → испорченный снимок. Поэтому чистим перед
записью. Старый снимок (бывшая активная БД) при этом освобождается на следующем
цикле — его же этапом 2.

Границы этапов оформлены контекст-менеджером _stage: он логирует начало и итог
этапа (с результатом и длительностью) и запоминает имя для PipelineError —
бизнес-код этапов не содержит журнальной обвязки.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import BaseModel

from app.config import settings
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.logging_config import get_logger
from app.repository.redis_repository import RedisRepository
from app.services.parser_service import ParserService

log = get_logger(__name__)

VedRecord = RatingVedModel | NotRatingVedModel


def record_to_key(record: VedRecord) -> str:
    """Маппер «запись → ключ Redis».

    ved_type — это Enum VedType; берём именно .value («Зачет»), т.к. в Python 3.12
    f-строка от члена str-Enum даёт «VedType.ZACHET», а читатель ищет по .value.
    """
    return f"{record.zach_number}:{record.ved_type.value}:{record.subject_name}"


class PipelineReport(BaseModel):
    """Итог одного цикла: что сделано на каждом этапе и сколько это заняло."""

    site_available: bool = False
    groups: int = 0
    urls: int = 0
    parsed_veds: int = 0
    empty_veds: int = 0  # нерабочие/пустые ведомости — штатный пропуск, не потеря
    failed_veds: int = 0  # сетевая ошибка / 429 после ретраев — реальная потеря
    total_records: int = 0
    swap_performed: bool = False
    links_s: float = 0.0
    parse_s: float = 0.0
    total_s: float = 0.0

    @property
    def loss_pct(self) -> float:
        return self.failed_veds / self.urls * 100 if self.urls else 0.0

    def summary(self) -> dict:
        """Поля отчёта в виде, пригодном для лога: округлённые тайминги и loss_pct."""
        data = self.model_dump()
        for key in ("links_s", "parse_s", "total_s"):
            data[key] = round(data[key], 1)
        data["loss_pct"] = round(self.loss_pct, 2)
        return data


class PipelineError(RuntimeError):
    """Ошибка цикла с привязкой к этапу, на котором он произошёл."""

    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"{stage}: {cause!r}")
        self.stage = stage


class ParsingPipeline:
    def __init__(self, parser: ParserService, repo: RedisRepository) -> None:
        self._parser = parser
        self._repo = repo
        self._stage_name = "initialization"

    @asynccontextmanager
    async def _stage(self, num: int, title: str) -> AsyncIterator[dict]:
        """Граница этапа: лог «— started», затем «— completed» с результатом и длительностью.

        Тело этапа складывает свой результат в отданный словарь; его поля попадают
        в строку завершения. Имя этапа запоминается для PipelineError.
        """
        self._stage_name = f"Stage {num}: {title}"
        log.info("%s — started", self._stage_name)
        t = time.monotonic()
        result: dict = {}
        yield result
        log.info("%s — completed", self._stage_name, **result, duration_s=round(time.monotonic() - t, 1))

    async def run(self) -> PipelineReport:
        """Выполняет цикл целиком; на любой ошибке поднимает PipelineError.

        Если сайт недоступен, отчёт возвращается с site_available=False
        и дальнейшие этапы не выполняются.
        """
        report = PipelineReport()
        t_start = time.monotonic()
        try:
            async with self._stage(1, "checking site availability") as r:
                report.site_available = await self._parser.check_site_availability()
                r["available"] = report.site_available
            if not report.site_available:
                log.warning("Site is unavailable, cycle skipped", url=settings.site.base_url)
                return report

            background_db = await self._repo.get_background_db()

            async with self._stage(2, "clearing background database") as r:
                r["db"] = await self._repo.flush_background()

            async with self._stage(3, "collecting vedomost links") as r:
                urls = await self._collect_links(report)
                r["groups"] = report.groups
                r["links"] = report.urls

            async with self._stage(4, "parsing records and saving to background database") as r:
                await self._parse_and_save(urls, background_db, report)
                r["parsed"] = report.parsed_veds
                r["empty"] = report.empty_veds
                r["failed"] = report.failed_veds
                r["records"] = report.total_records

            async with self._stage(5, "switching active database") as r:
                old, new = await self._repo.switch_active_db()
                report.swap_performed = True
                r["old"] = old
                r["new"] = new
        except Exception as exc:
            raise PipelineError(self._stage_name, exc) from exc
        finally:
            report.total_s = time.monotonic() - t_start
        return report

    # --- этапы ---

    async def _collect_links(self, report: PipelineReport) -> list[str]:
        t = time.monotonic()
        links = await self._parser.collect_ved_links()
        urls = [url for group_urls in links.values() for url in group_urls]
        report.groups = len(links)
        report.urls = len(urls)
        report.links_s = time.monotonic() - t
        return urls

    async def _parse_and_save(self, urls: list[str], background_db: int, report: PipelineReport) -> None:
        sem = asyncio.Semaphore(settings.scraper.concurrency)
        completed = 0

        async def handle(url: str) -> None:
            nonlocal completed
            async with sem:
                records = await self._parser.parse_ved(url)
            if records is None:
                report.failed_veds += 1
            elif records:
                report.parsed_veds += 1
                await self._repo.set_records(
                    background_db,
                    {record_to_key(record): record.model_dump() for record in records},
                )
                report.total_records += len(records)
            else:
                report.empty_veds += 1

            completed += 1
            if completed % 250 == 0 or completed == len(urls):
                log.info(
                    "Parsing progress",
                    done=f"{completed}/{len(urls)}",
                    pct=round(completed / len(urls) * 100, 1),
                    records=report.total_records,
                )

        t = time.monotonic()
        await asyncio.gather(*(handle(url) for url in urls))
        report.parse_s = time.monotonic() - t
