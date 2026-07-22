"""Триггер планировщика: создаёт зависимости и запускает ParsingPipeline."""

import asyncio
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.repository.redis_repository import RedisRepository
from app.services.parser_service import ParserService
from app.services.parsing_pipeline import ParsingPipeline, PipelineError




logger = logging.getLogger(__name__)

# Гарантирует, что в один момент времени выполняется ровно один цикл парсинга
# (подстраховка к max_instances=1 планировщика на случай ручного запуска).
_running = asyncio.Lock()




async def run_parsing_cycle() -> None:
    """Полный цикл парсинга."""

    if _running.locked():
        logger.info("Parsing cycle is already running, skipping")
        return

    async with _running:
        logger.info("Start parsing cycle")
        repo = RedisRepository()
        try:
            async with ParserService() as parser:
                report = await ParsingPipeline(parser, repo).run()
        except PipelineError as exc:
            logger.exception(
                "Parsing cycle failed during stage: '%s'. Switch db not performed", exc.stage
            )
            return
        finally:
            await repo.close()

        if not report.site_available:
            next_run = (
                datetime.now() + timedelta(minutes=settings.scheduler_interval_minutes)
            ).strftime("%Y-%m-%d %H:%M:%S")
            logger.warning(
                "Site %s is unavailable. Parsing cycle postponed until next run at %s",
                settings.rating_base_url, next_run,
            )
            return

        logger.info(
            "Parsing cycle completed in %.1f s | groups: %d | veds parsed/empty/failed: %d/%d/%d (%.2f%% loss) | records: %d",
            report.total_s, report.groups, report.parsed_veds, report.empty_veds,
            report.failed_veds, report.loss_pct, report.total_records,
        )
