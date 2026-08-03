from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import dispose_engine, init_models, session_scope
from app.logging_config import get_logger, print_banner, setup_logging
from app.repository.rating_repository import RatingRepository
from app.routers import rating_router, schedule_router, students_router
from app.scheduler.jobs import run_parsing_cycle

print_banner()
setup_logging()
log = get_logger(__name__)

# Небольшая задержка первого («немедленного») цикла: даём uvicorn договорить свой
# стартовый баннер ("Uvicorn running on ...") до старта тяжёлого цикла — иначе job
# на том же event loop влезает в хвост стартовых логов.
_FIRST_RUN_DELAY_S = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Application start up", year=settings.parsing.year, semester=settings.parsing.semester)
    log.info("Swagger UI documentation is available at: http://localhost:8000/docs")

    # Движок и недостающие таблицы. На существующей базе ничего не пересоздаётся.
    await init_models()

    # Сервисы больше не живут в app.state: их собирает цепочка зависимостей
    # сессия → репозиторий → сервис на каждый запрос (см. app/db/session.py).
    async with session_scope() as session:
        counts = await RatingRepository(session).counts()
    log.info("Snapshot on start", **counts)

    # Если снапшота ещё нет — первый запуск парсинга сразу после старта
    # (с небольшой задержкой, чтобы не влезть в стартовые логи uvicorn).
    empty = all(n == 0 for n in counts.values())
    first_run = datetime.now() + timedelta(seconds=_FIRST_RUN_DELAY_S) if empty else None
    if empty:
        log.info("Database is empty — parsing cycle will run shortly after startup", delay_s=_FIRST_RUN_DELAY_S)
    else:
        log.info(
            "Database already contains data — immediate parsing cycle skipped",
            next_run_in_min=settings.scheduler.interval_minutes,
        )

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_parsing_cycle,
        trigger="interval",
        minutes=settings.scheduler.interval_minutes,
        id="parsing_cycle",
        max_instances=1,
        coalesce=True,
        next_run_time=first_run,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    log.info("Scheduler started", interval_min=settings.scheduler.interval_minutes)

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await dispose_engine()
        log.info("Application stopped")


app = FastAPI(title="VSUET Rating", lifespan=lifespan)
# CORS для локального фронтенда (Vite/CRA/иные dev-серверы на localhost).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(students_router.router)
app.include_router(rating_router.router)
app.include_router(schedule_router.router)
