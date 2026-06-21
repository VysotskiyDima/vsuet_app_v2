"""Планируемый job парсинга (раз в 30 минут).

Этапы:
  1. Проверка доступности сайта — если недоступен, выйти до следующего запуска.
  2. Очистить фоновую БД (мера предосторожности), собрать ссылки на ведомости по всем группам.
  3. Конкурентно (под общим семафором) спарсить ведомости и записать каждую
     запись в фоновую БД под ключом <zach_number>:<ved_type>:<subject_name>.
  4. По успешному завершению — поменять активную и фоновую БД ролями.
     При критической ошибке переключение не выполняется.
"""

import asyncio
from datetime import datetime, timedelta
import logging
import random
import time

from app.config import settings
from app.logging_config import trace_ctx
from app.repository.redis_repository import RedisRepository
from app.services.parser_service import CONCURRENCY, ParserService





logger = logging.getLogger(__name__)

# гарантирует, что async with _running: в один момент времени может выполнять 
# только одна корутина (в любой момент времени выполняется ровно один цикл парсинга).
_running = asyncio.Lock() 




def record_to_key(record: dict) -> str:
    """Маппер «запись → ключ Redis»."""
    return f"{record['zach_number']}:{record['ved_type']}:{record['subject_name']}"


async def run_parsing_cycle() -> None:
    """Полный цикл парсинга."""

    if _running.locked():
        logger.info("Parsing cycle is already running, skipping")
        return

    async with _running:
        # Генерируем 10-значный TRANSACTION-ID для трассировки логов планировщика
        tx_id = str(random.randint(10**9, 10**10 - 1))
        token = trace_ctx.set({"TRANSACTION-ID": tx_id})
        
        t_start = time.monotonic()
        logger.info("Start parsing cycle")

        repo = None
        stage = "Initialization"
        try:
            # Этап 1 — доступность сайта.
            stage = "Stage 1: Checking site availability"
            logger.info("Stage 1: Checking site https://rating.vsuet.ru/web/ved/Default.aspx availability")
            
            async with ParserService() as parser:
                if not await parser.check_site_availability():
                    next_run = (datetime.now() + timedelta(minutes=settings.scheduler_interval_minutes)).strftime("%Y-%m-%d %H:%M:%S")
                    logger.warning("Site https://rating.vsuet.ru/web/ved/Default.aspx is unavailable. Parsing cycle postponed until next run at %s", next_run)
                    return
                logger.info("Stage 1 success: site https://rating.vsuet.ru/web/ved/Default.aspx available")

                # Этап 2 — очистка фоновой БД и сбор ссылок.
                stage = "Stage 2: Clearing background DB and collecting links"
                logger.info("Stage 2: Initializing Redis repository and collecting list of vedomost URLs")
                
                try:
                    repo = RedisRepository()
                    logger.info("Redis repository initialized successfully")
                except Exception as e:
                    logger.error("Failed to initialize Redis repository: %s", e, exc_info=True)
                    return

                background_db = await repo.get_background_db()
                await repo.flush_background()

                t_links = time.monotonic()
                links = await parser.collect_ved_links()
                urls = [url for group_urls in links.values() for url in group_urls]
                logger.info(
                    "Stage 2 collect ved links completed in %.1f s | groups: %d | links: %d",
                    time.monotonic() - t_links, len(links), len(urls),
                )

                # Этап 3 — конкурентный парсинг и запись в фоновую БД.
                stage = "Stage 3: Parsing records and saving to background DB"
                logger.info("Stage 3: Parsing of %d URLs with concurrency=%d", len(urls), CONCURRENCY)
                
                sem = asyncio.Semaphore(CONCURRENCY)
                total_records = 0
                parsed_veds = 0
                skipped_veds = 0

                async def handle(url: str) -> None:
                    nonlocal total_records, parsed_veds, skipped_veds
                    async with sem:
                        records = await parser.parse_ved(url)
                    if records:
                        parsed_veds += 1
                        for record in records:
                            await repo.set_record(background_db, record_to_key(record), record)
                            total_records += 1
                    else:
                        skipped_veds += 1

                t_parse = time.monotonic()
                await asyncio.gather(*(handle(url) for url in urls))
                logger.info(
                    "Stage 3 parse and save completed in %.1f s | parsed veds: %d | skipped veds: %d | total records in DB: %d",
                    time.monotonic() - t_parse, parsed_veds, skipped_veds, total_records,
                )

            # Этап 4 — переключение активной/фоновой БД.
            stage = "Stage 4: Switching active database"
            logger.info("Stage 4: Swapping active and background databases...")
            
            t_swap = time.monotonic()
            await repo.switch_active_db()
            # Очищаем новую фоновую БД после переключения (высвобождаем память Redis)
            await repo.flush_background()
            logger.info(
                "Stage 4 switch active db completed in %.1f s | total time: %.1f s",
                time.monotonic() - t_swap, time.monotonic() - t_start,
            )
        except Exception:
            logger.exception(
                "Parsing cycle failed (%.1f s) during stage: '%s'. Switch db not performed",
                time.monotonic() - t_start, stage
            )
        finally:
            if repo is not None:
                await repo.close()
            trace_ctx.reset(token)
