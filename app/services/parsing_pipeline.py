"""Пайплайн полного цикла парсинга: четыре этапа от проверки сайта до swap БД.

Вынесен из app/scheduler/jobs.py: планировщик только триггерит запуск по
расписанию, а вся логика цикла и его метрики живут здесь. Зависимостями
(ParserService, RedisRepository) владеет вызывающий — пайплайн не открывает
и не закрывает ресурсы, поэтому легко тестируется на подменах.
"""

import asyncio
import logging
import time

from pydantic import BaseModel

from app.config import settings
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.repository.redis_repository import RedisRepository
from app.services.parser_service import CONCURRENCY, ParserService

logger = logging.getLogger(__name__)

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
    empty_veds: int = 0   # нерабочие/пустые ведомости — штатный пропуск, не потеря
    failed_veds: int = 0  # сетевая ошибка / 429 после ретраев — реальная потеря
    total_records: int = 0
    swap_performed: bool = False
    links_s: float = 0.0
    parse_s: float = 0.0
    total_s: float = 0.0

    @property
    def loss_pct(self) -> float:
        return self.failed_veds / self.urls * 100 if self.urls else 0.0


class PipelineError(RuntimeError):
    """Ошибка цикла с привязкой к этапу, на котором он произошёл."""

    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"{stage}: {cause!r}")
        self.stage = stage


class ParsingPipeline:
    def __init__(self, parser: ParserService, repo: RedisRepository) -> None:
        self._parser = parser
        self._repo = repo

    async def run(self) -> PipelineReport:
        """Выполняет цикл целиком; на любой ошибке поднимает PipelineError.

        Если цикл дошёл до конца, отчёт полностью заполнен; если сайт недоступен,
        отчёт возвращается с site_available=False и swap не выполняется.
        """
        report = PipelineReport()
        t_start = time.monotonic()
        stage = "Stage 1: Checking site availability"
        try:
            logger.info("Stage 1: Checking site %s availability", settings.rating_base_url)
            if not await self._parser.check_site_availability():
                logger.warning("Site %s is unavailable", settings.rating_base_url)
                return report
            report.site_available = True
            logger.info("Stage 1 success: site %s available", settings.rating_base_url)

            stage = "Stage 2: Clearing background DB and collecting links"
            urls, background_db = await self._collect_links(report)

            stage = "Stage 3: Parsing records and saving to background DB"
            await self._parse_and_save(urls, background_db, report)

            stage = "Stage 4: Switching active database"
            await self._swap(report)
        except Exception as exc:
            raise PipelineError(stage, exc) from exc
        finally:
            report.total_s = time.monotonic() - t_start
        return report

    # --- этапы ---

    async def _collect_links(self, report: PipelineReport) -> tuple[list[str], int]:
        logger.info("Stage 2: Clearing background DB and collecting vedomost URLs")
        background_db = await self._repo.get_background_db()
        await self._repo.flush_background()

        t = time.monotonic()
        links = await self._parser.collect_ved_links()
        urls = [url for group_urls in links.values() for url in group_urls]
        report.groups = len(links)
        report.urls = len(urls)
        report.links_s = time.monotonic() - t
        logger.info(
            "Stage 2 collect ved links completed in %.1f s | groups: %d | links: %d",
            report.links_s, report.groups, report.urls,
        )
        return urls, background_db

    async def _parse_and_save(self, urls: list[str], background_db: int, report: PipelineReport) -> None:
        logger.info("Stage 3: Parsing of %d URLs with concurrency=%d", len(urls), CONCURRENCY)
        sem = asyncio.Semaphore(CONCURRENCY)
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
                logger.info(
                    "Parsing progress: %d/%d vedomosts processed (%.1f%%) | records in DB: %d",
                    completed, len(urls), (completed / len(urls) * 100), report.total_records,
                )

        t = time.monotonic()
        await asyncio.gather(*(handle(url) for url in urls))
        report.parse_s = time.monotonic() - t
        logger.info(
            "Stage 3 parse and save completed in %.1f s | parsed veds: %d | empty veds: %d | failed veds: %d (%.2f%% loss) | total records in DB: %d",
            report.parse_s, report.parsed_veds, report.empty_veds,
            report.failed_veds, report.loss_pct, report.total_records,
        )

    async def _swap(self, report: PipelineReport) -> None:
        logger.info("Stage 4: Swapping active and background databases...")
        t = time.monotonic()
        await self._repo.switch_active_db()
        # Очищаем новую фоновую БД после переключения (высвобождаем память Redis)
        await self._repo.flush_background()
        report.swap_performed = True
        logger.info("Stage 4 switch active db completed in %.1f s", time.monotonic() - t)
