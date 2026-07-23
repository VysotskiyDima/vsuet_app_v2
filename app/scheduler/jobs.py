"""Триггер планировщика: создаёт зависимости и запускает ParsingPipeline."""

import asyncio
from datetime import datetime, timedelta

from app.config import settings
from app.logging_config import get_logger
from app.repository.redis_repository import RedisRepository
from app.services.parser_service import ParserService
from app.services.parsing_pipeline import ParsingPipeline, PipelineError

log = get_logger(__name__)

# Гарантирует, что в один момент времени выполняется ровно один цикл парсинга
# (подстраховка к max_instances=1 планировщика на случай ручного запуска).
_running = asyncio.Lock()


async def run_parsing_cycle() -> None:
    """Полный цикл парсинга."""

    if _running.locked():
        log.info("Parsing cycle is already running, skipping")
        return

    async with _running:
        log.info("Start parsing cycle")
        repo = RedisRepository()
        try:
            async with ParserService() as parser:
                report = await ParsingPipeline(parser, repo).run()
        except PipelineError as exc:
            log.exception("Parsing cycle failed, switch db not performed", stage=exc.stage)
            return
        finally:
            await repo.close()

        if not report.site_available:
            next_run = (datetime.now() + timedelta(minutes=settings.scheduler.interval_minutes)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            log.warning("Parsing cycle postponed", url=settings.site.base_url, next_run=next_run)
            return

        log.info("Parsing cycle completed", **report.summary())
