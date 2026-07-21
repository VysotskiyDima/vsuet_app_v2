import asyncio
from datetime import datetime, timedelta
import logging
import time

from app.config import settings
from app.repository.redis_repository import RedisRepository
from app.services.parser_service import CONCURRENCY, ParserService

from pydantic import BaseModel





logger = logging.getLogger(__name__)

# гарантирует, что async with _running: в один момент времени может выполнять 
# только одна корутина (в любой момент времени выполняется ровно один цикл парсинга).
_running = asyncio.Lock() 




def record_to_key(record: BaseModel) -> str:
    """Маппер «запись → ключ Redis».

    ved_type — это Enum VedType; берём именно .value («Зачет»), т.к. в Python 3.12
    f-строка от члена str-Enum даёт «VedType.ZACHET», а читатель ищет по .value.
    """
    return f"{record.zach_number}:{record.ved_type.value}:{record.subject_name}"


async def run_parsing_cycle() -> None:
    """Полный цикл парсинга."""

    if _running.locked():
        logger.info("Parsing cycle is already running, skipping")
        return

    async with _running:
        t_start = time.monotonic()
        logger.info("Start parsing cycle")

        repo = None
        stage = "Initialization"
        try:
            # Этап 1 — доступность сайта.
            stage = "Stage 1: Checking site availability"
            logger.info("Stage 1: Checking site %s availability", settings.rating_base_url)
            
            async with ParserService() as parser:
                if not await parser.check_site_availability():
                    next_run = (datetime.now() + timedelta(minutes=settings.scheduler_interval_minutes)).strftime("%Y-%m-%d %H:%M:%S")
                    logger.warning("Site %s is unavailable. Parsing cycle postponed until next run at %s", settings.rating_base_url, next_run)
                    return
                logger.info("Stage 1 success: site %s available", settings.rating_base_url)

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
                empty_veds = 0   # нерабочие/пустые ведомости — штатный пропуск, не потеря
                failed_veds = 0  # сетевая ошибка / 429 после ретраев — реальная потеря
                completed_veds = 0

                async def handle(url: str) -> None:
                    nonlocal total_records, parsed_veds, empty_veds, failed_veds, completed_veds
                    async with sem:
                        records = await parser.parse_ved(url)
                    if records is None:
                        failed_veds += 1
                    elif records:
                        parsed_veds += 1
                        await repo.set_records(
                            background_db,
                            {record_to_key(record): record.model_dump() for record in records},
                        )
                        total_records += len(records)
                    else:
                        empty_veds += 1

                    completed_veds += 1
                    if completed_veds % 250 == 0 or completed_veds == len(urls):
                        logger.info(
                            "Parsing progress: %d/%d vedomosts processed (%.1f%%) | records in DB: %d",
                            completed_veds, len(urls), (completed_veds / len(urls) * 100), total_records
                        )

                t_parse = time.monotonic()
                await asyncio.gather(*(handle(url) for url in urls))
                loss_pct = (failed_veds / len(urls) * 100) if urls else 0.0
                logger.info(
                    "Stage 3 parse and save completed in %.1f s | parsed veds: %d | empty veds: %d | failed veds: %d (%.2f%% loss) | total records in DB: %d",
                    time.monotonic() - t_parse, parsed_veds, empty_veds, failed_veds, loss_pct, total_records,
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
