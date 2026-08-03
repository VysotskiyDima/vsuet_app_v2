"""Движок, фабрика сессий и способы её получить.

Единственное место, где создаётся подключение к БД. Наружу отдаются два входа,
оба через одну фабрику:

* get_session — зависимость FastAPI: сессия на время запроса, закрывается сама;
* session_scope — контекст-менеджер для фонового кода (планировщик, пайплайн),
  где механики Depends нет.

Драйвер асинхронный (aiosqlite), поэтому обёрток над потоками здесь нет: и API,
и цикл парсинга работают с БД прямо в event loop.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base
from app.logging_config import get_logger

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def db_path() -> Path:
    return Path(settings.db.path)


def _apply_pragmas(engine: AsyncEngine) -> None:
    """PRAGMA задаются на каждое новое подключение пула.

    WAL — ключевой режим: читатели не блокируются писателем, поэтому долгий цикл
    парсинга не мешает отдавать рейтинг из прежнего снапшота.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL вместо FULL: снапшот перестраивается каждым циклом, потеря
            # последних транзакций при отказе питания некритична.
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute(f"PRAGMA busy_timeout={settings.db.busy_timeout_ms}")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def init_engine() -> AsyncEngine:
    """Создаёт движок и фабрику сессий. Вызывается один раз на старте."""
    global _engine, _session_factory

    if _engine is not None:
        return _engine

    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    _engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        # Пул на несколько читающих подключений; писатель берёт своё из того же
        # пула и держит его на всё время транзакции цикла.
        pool_size=settings.db.pool_size,
        max_overflow=settings.db.max_overflow,
        pool_pre_ping=True,
        future=True,
    )
    _apply_pragmas(_engine)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    log.debug("Database engine created", path=str(path), pool_size=settings.db.pool_size)
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий. До init_engine() обращаться нельзя."""
    if _session_factory is None:
        raise RuntimeError("Движок не инициализирован: сначала вызовите init_engine()")
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI: сессия живёт ровно один запрос."""
    async with session_factory()() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Сессия для кода вне запроса: планировщика и цикла парсинга."""
    async with session_factory()() as session:
        yield session


async def init_models() -> None:
    """Создаёт недостающие таблицы и индексы.

    checkfirst оставлен включённым по умолчанию: на существующей базе ничего не
    пересоздаётся и данные остаются на месте.
    """
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database ready", path=str(db_path()))


async def dispose_engine() -> None:
    """Закрывает пул подключений при остановке приложения."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        log.debug("Database engine disposed")
