"""Точка входа FastAPI: подключает роутер и запускает планировщик парсинга."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logging_config import setup_logging, trace_ctx
from app.repository.redis_repository import RedisRepository
from app.routers import rating_router, students_router
from app.scheduler.jobs import run_parsing_cycle
from app.services.rating_service import RatingService
from app.services.student_service import StudentService




setup_logging()
logger = logging.getLogger(__name__)




class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Извлекаем или генерируем REQUEST-UUID
        request_uuid = request.headers.get("X-Request-ID") or request.headers.get("X-Request-Uuid")
        if not request_uuid:
            request_uuid = uuid.uuid4().hex

        # Извлекаем или генерируем CORRELATION-UUID
        correlation_uuid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Correlation-Uuid")
        if not correlation_uuid:
            correlation_uuid = uuid.uuid4().hex

        # Сохраняем идентификаторы в контекст логгера
        token = trace_ctx.set({
            "REQUEST-UUID": request_uuid,
            "CORRELATION-UUID": correlation_uuid
        })
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            process_time = (time.perf_counter() - start_time) * 1000
            logger.info(
                "%s %s - %d in %.2f ms",
                request.method,
                request.url.path,
                response.status_code,
                process_time,
            )
            response.headers["X-Request-ID"] = request_uuid
            response.headers["X-Correlation-ID"] = correlation_uuid
            return response
        except Exception as e:
            process_time = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "Unhandled exception during request processing: %s %s (failed in %.2f ms)",
                request.method,
                request.url.path,
                process_time,
            )
            raise e
        finally:
            trace_ctx.reset(token)


async def _is_db_empty(repo: RedisRepository) -> bool:
    """True, если обе data-БД пусты (первый запуск / свежий Redis)."""
    for db_num, client in repo._clients.items():
        size = await client.dbsize()
        if size > 0:
            return False
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Application start up  |  year=%s  semester=%s",
        settings.parsing_year,
        settings.parsing_semester,
    )
    logger.info("Swagger UI documentation is available at: http://localhost:8000/docs")

    app.state.repo = RedisRepository()
    app.state.rating_service = RatingService(app.state.repo)
    app.state.student_service = StudentService(app.state.repo)

    # Проверяем состояние базы данных на старте
    active_db = await app.state.repo.get_active_db()
    active_client = app.state.repo._clients[active_db]
    db_size = await active_client.dbsize()
    logger.info("Active database: DB %d  |  Keys count: %d", active_db, db_size)

    # Если обе data-БД пусты — первый запуск парсинга немедленно.
    empty = await _is_db_empty(app.state.repo)
    first_run = datetime.now() if empty else None
    if empty:
        logger.info("Redis is empty — parsing cycle will run immediately")
    else:
        logger.info(
            "Database already contains data — immediate parsing cycle skipped. "
            "Next scheduled run will start in %d minutes",
            settings.scheduler_interval_minutes,
        )

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_parsing_cycle,
        trigger="interval",
        minutes=settings.scheduler_interval_minutes,
        id="parsing_cycle",
        max_instances=1,
        coalesce=True,
        next_run_time=first_run,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "Scheduler started, interval=%d min", settings.scheduler_interval_minutes
    )

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await app.state.repo.close()
        logger.info("Application stopped")


app = FastAPI(title="VSUET Rating Backend", lifespan=lifespan)
# CORS для локального фронтенда (Vite/CRA/иные dev-серверы на localhost).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TracingMiddleware)
app.include_router(students_router.router)
app.include_router(rating_router.router)

