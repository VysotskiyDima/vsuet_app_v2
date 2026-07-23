"""Точка входа FastAPI: подключает роутер и запускает планировщик парсинга."""

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders

from app.config import settings
from app.logging_config import get_logger, print_banner, setup_logging, trace_ctx
from app.repository.redis_repository import RedisRepository
from app.routers import rating_router, students_router
from app.scheduler.jobs import run_parsing_cycle
from app.services.rating_service import RatingService
from app.services.student_service import StudentService

print_banner()
setup_logging()
log = get_logger(__name__)

# Небольшая задержка первого («немедленного») цикла: даём uvicorn договорить свой
# стартовый баннер ("Uvicorn running on ...") до старта тяжёлого цикла — иначе job
# на том же event loop влезает в хвост стартовых логов.
_FIRST_RUN_DELAY_S = 3


class TracingMiddleware:
    """Один REQUEST-UUID на запрос: в контекст логов, в ответ, в access-лог.

    Pure-ASGI, а не BaseHTTPMiddleware: тот выполняет приложение в отдельной
    таске, из-за чего contextvars (наша trace_ctx) распространяются
    непредсказуемо, а BackgroundTasks выполняются уже после сброса контекста
    (см. обсуждения starlette#1729, starlette#2160). Correlation-ID не ведём:
    сервис — монолит, вышестоящих систем, передающих свой ID, нет.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # X-Request-ID уважаем, если пришёл (например, от nginx), иначе свой.
        request_uuid = Headers(scope=scope).get("x-request-id") or uuid.uuid4().hex
        token = trace_ctx.set({"REQUEST-UUID": request_uuid})
        start_time = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_uuid
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
            process_time = (time.perf_counter() - start_time) * 1000
            log.info(
                "Request handled",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                ms=round(process_time, 2),
            )
        except Exception:
            process_time = (time.perf_counter() - start_time) * 1000
            log.exception(
                "Unhandled exception during request processing",
                method=scope["method"],
                path=scope["path"],
                ms=round(process_time, 2),
            )
            raise
        finally:
            trace_ctx.reset(token)


async def _is_db_empty(repo: RedisRepository) -> bool:
    """True, если обе data-БД пусты (первый запуск / свежий Redis)."""
    for client in repo._clients.values():
        if await client.dbsize() > 0:
            return False
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Application start up", year=settings.parsing.year, semester=settings.parsing.semester)
    log.info("Swagger UI documentation is available at: http://localhost:8000/docs")

    app.state.repo = RedisRepository()
    app.state.rating_service = RatingService(app.state.repo)
    app.state.student_service = StudentService(app.state.repo)

    # Проверяем состояние базы данных на старте
    active_db = await app.state.repo.get_active_db()
    active_client = app.state.repo._clients[active_db]
    db_size = await active_client.dbsize()
    log.info("Active database", db=active_db, keys=db_size)

    # Если обе data-БД пусты — первый запуск парсинга сразу после старта
    # (с небольшой задержкой, чтобы не влезть в стартовые логи uvicorn).
    empty = await _is_db_empty(app.state.repo)
    first_run = datetime.now() + timedelta(seconds=_FIRST_RUN_DELAY_S) if empty else None
    if empty:
        log.info("Redis is empty — parsing cycle will run shortly after startup", delay_s=_FIRST_RUN_DELAY_S)
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
        await app.state.repo.close()
        log.info("Application stopped")


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
