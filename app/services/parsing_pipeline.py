"""Пайплайн полного цикла парсинга: четыре этапа от проверки сайта до коммита.

Вынесен из app/scheduler/jobs.py: планировщик только триггерит запуск по
расписанию, а вся логика цикла и его метрики живут здесь. Зависимостями
(ParserService, RatingRepository) владеет вызывающий — пайплайн не открывает
и не закрывает ресурсы, поэтому легко тестируется на подменах.

Этапы: 1) доступность сайта, 2) сбор ссылок по группам, 3) парсинг ведомостей
с записью в снапшот, 4) фиксация снапшота.

Чем это отличается от прежней версии на Redis. Там этапов было пять: перед
записью приходилось вручную чистить фоновую БД, а в конце — переключать
указатель активной, потому что у Redis нет транзакций и «полузаписанный» снимок
иначе стал бы виден читателям. SQLite решает это сам: всё пишется в одной
транзакции, до COMMIT читатели видят прежний снимок, а обрыв процесса посреди
цикла откатывается движком. Поэтому очистка и переключение исчезли, а появился
этап фиксации.

Заодно на этапе 3 попутно собирается связка «зачётка → группа»: ссылки уже
разложены по группам, а номера зачёток есть в записях — дополнительных запросов
к сайту не требуется (см. app/services/group_extractor.py).

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
from app.logging_config import get_logger
from app.repository.rating_repository import RatingRepository
from app.repository.snapshot_repository import SnapshotRepository
from app.services.group_extractor import GroupExtractor
from app.services.parser_service import ParserService

log = get_logger(__name__)


class PipelineReport(BaseModel):
    """Итог одного цикла: что сделано на каждом этапе и сколько это заняло."""

    site_available: bool = False
    groups: int = 0
    urls: int = 0
    parsed_veds: int = 0
    empty_veds: int = 0  # нерабочие/пустые ведомости — штатный пропуск, не потеря
    failed_veds: int = 0  # сетевая ошибка / 429 после ретраев — реальная потеря
    total_records: int = 0
    rating_rows: int = 0  # строк в таблице после коммита, а не число вставок
    grade_rows: int = 0
    duplicate_keys: int = 0  # записей схлопнулось по ключу: пересдачи, общие ведомости
    skipped_blank: int = 0  # служебные строки ведомости без номера зачётки
    students_with_group: int = 0
    group_conflicts: int = 0  # зачётка встретилась более чем в одной группе
    snapshot_committed: bool = False
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
    """Зависимостями владеет вызывающий: пайплайн не открывает и не закрывает
    ни HTTP-клиент, ни сессию БД, поэтому легко подменяется в тестах.

    Репозитория два: snapshot пишет новый снимок в своей транзакции, reader
    считает итоговые строки после коммита.
    """

    def __init__(
        self,
        parser: ParserService,
        snapshot: SnapshotRepository,
        reader: RatingRepository,
    ) -> None:
        self._parser = parser
        self._snapshot = snapshot
        self._reader = reader
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
        opened = False
        try:
            async with self._stage(1, "checking site availability") as r:
                report.site_available = await self._parser.check_site_availability()
                r["available"] = report.site_available
            if not report.site_available:
                log.warning("Site is unavailable, cycle skipped", url=settings.site.base_url)
                return report

            async with self._stage(2, "collecting vedomost links") as r:
                links = await self._collect_links(report)
                r["groups"] = report.groups
                r["links"] = report.urls

            async with self._stage(3, "parsing records into snapshot") as r:
                await self._snapshot.begin()
                opened = True
                await self._parse_and_save(links, report)
                r["parsed"] = report.parsed_veds
                r["empty"] = report.empty_veds
                r["failed"] = report.failed_veds
                r["records"] = report.total_records
                r["students_with_group"] = report.students_with_group
                r["group_conflicts"] = report.group_conflicts
                r["skipped_blank"] = report.skipped_blank

            async with self._stage(4, "committing snapshot") as r:
                inserted = self._snapshot.rating_rows + self._snapshot.grade_rows
                await self._snapshot.commit()
                opened = False
                report.snapshot_committed = True
                # Считаем строки уже после коммита: INSERT OR REPLACE схлопывает
                # повторы по ключу, поэтому число вставок больше числа строк.
                counts = await self._reader.counts()
                report.rating_rows = counts["rating_record"]
                report.grade_rows = counts["grade_record"]
                report.duplicate_keys = inserted - report.rating_rows - report.grade_rows
                r["rating_rows"] = report.rating_rows
                r["grade_rows"] = report.grade_rows
                r["group_rows"] = counts["student_group"]
                r["duplicate_keys"] = report.duplicate_keys
        except Exception as exc:
            # Снапшот не зафиксирован — откатываем, читатели остаются на прежних данных.
            if opened:
                await self._snapshot.rollback()
            raise PipelineError(self._stage_name, exc) from exc
        finally:
            report.total_s = time.monotonic() - t_start
        return report

    # --- этапы ---

    async def _collect_links(self, report: PipelineReport) -> dict[str, list[str]]:
        t = time.monotonic()
        links = await self._parser.collect_ved_links()
        report.groups = len(links)
        report.urls = sum(len(urls) for urls in links.values())
        report.links_s = time.monotonic() - t
        return links

    async def _parse_and_save(
        self,
        links: dict[str, list[str]],
        report: PipelineReport,
    ) -> None:
        """Разбирает ведомости и пишет их в открытый снапшот.

        Ведомость обрабатывается вместе с названием своей группы, поэтому здесь
        же наполняется связка «зачётка → группа» — без обращений к сайту.
        """
        sem = asyncio.Semaphore(settings.scraper.concurrency)
        extractor = GroupExtractor()
        # Плоский список пар (группа, ссылка): ссылки разных групп идут в общий
        # пул, чтобы семафор равномерно грузил сайт, а не шёл группа за группой.
        tasks = [(group, url) for group, urls in links.items() for url in urls]
        completed = 0

        async def handle(group: str, url: str) -> None:
            nonlocal completed
            async with sem:
                records = await self._parser.parse_ved(url)

            if records is None:
                report.failed_veds += 1
            elif records:
                report.parsed_veds += 1
                extractor.feed(group, records)
                await self._snapshot.add_records(records)
                report.total_records += len(records)
            else:
                report.empty_veds += 1

            completed += 1
            if completed % 250 == 0 or completed == len(tasks):
                log.info(
                    "Parsing progress",
                    done=f"{completed}/{len(tasks)}",
                    pct=round(completed / len(tasks) * 100, 1),
                    records=report.total_records,
                )

        t = time.monotonic()
        await asyncio.gather(*(handle(group, url) for group, url in tasks))
        report.parse_s = time.monotonic() - t

        # Связку пишем одним куском в конце: она нужна целиком, а её объём мал —
        # одна строка на студента против десятков строк рейтинга.
        await self._snapshot.add_groups(extractor.pairs())
        report.students_with_group = extractor.students
        report.group_conflicts = extractor.ambiguous
        report.skipped_blank = self._snapshot.skipped_rows
