import json
import logging

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_ACTIVE_PTR_KEY = "active_db"
_SCAN_COUNT = 500


def _escape_glob(value: str) -> str:
    """Экранирует спецсимволы glob, чтобы префикс матчился буквально."""
    out = []
    for ch in value:
        if ch in "*?[]\\":
            out.append("\\")
        out.append(ch)
    return "".join(out)


class RedisRepository:
    def __init__(self) -> None:
        self._data_dbs = (settings.redis_db_0, settings.redis_db_1)
        self._clients: dict[int, redis.Redis] = {
            db: redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=db,
                decode_responses=True,
            )
            for db in self._data_dbs
        }
        self._meta = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_meta_db,
            decode_responses=True,
        )
        logger.debug(
            "Redis clients created  |  host=%s:%s  data_dbs=%s  meta_db=%s",
            settings.redis_host,
            settings.redis_port,
            self._data_dbs,
            settings.redis_meta_db,
        )

    async def close(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        await self._meta.aclose()
        logger.debug("Redis clients closed")

    # --- управление активной/фоновой БД -------------------------------------

    async def get_active_db(self) -> int:
        """Номер активной БД. По умолчанию — первая из пары."""
        value = await self._meta.get(_ACTIVE_PTR_KEY)
        if value is None:
            return self._data_dbs[0]
        return int(value)

    async def get_background_db(self) -> int:
        active = await self.get_active_db()
        return self._data_dbs[1] if active == self._data_dbs[0] else self._data_dbs[0]

    async def switch_active_db(self) -> None:
        """Меняет активную и фоновую БД ролями (обновляет указатель)."""
        background = await self.get_background_db()
        await self._meta.set(_ACTIVE_PTR_KEY, background)
        logger.info(
            "Active DB switched: %d -> %d",
            self._data_dbs[0] if background == self._data_dbs[1] else self._data_dbs[1],
            background,
        )

    async def flush_background(self) -> None:
        background = await self.get_background_db()
        await self._clients[background].flushdb()
        logger.info("Background DB %d flushed", background)

    async def set_records(self, db: int, items: dict[str, dict]) -> None:
        """Пакетная запись: все ключи одной пачкой через pipeline (один round-trip)."""
        if not items:
            return
        pipe = self._clients[db].pipeline(transaction=False)
        for key, value in items.items():
            pipe.set(key, json.dumps(value, ensure_ascii=False))
        await pipe.execute()
        logger.debug("SET pipeline db=%d  keys=%d", db, len(items))

    # --- чтение для endpoints ------------------------------------------------

    async def _active_client(self) -> redis.Redis:
        return self._clients[await self.get_active_db()]

    async def get_by_prefix(self, prefix: str) -> list[dict]:
        """Все значения активной БД по ключам с данным префиксом (SCAN + MGET)."""
        client = await self._active_client()
        pattern = _escape_glob(prefix) + "*"
        keys: list[str] = []
        async for key in client.scan_iter(match=pattern, count=_SCAN_COUNT):
            keys.append(key)
        if not keys:
            logger.debug("get_by_prefix(%s) → 0 keys", prefix)
            return []
        values = await client.mget(keys)
        result = [json.loads(v) for v in values if v is not None]
        logger.debug("get_by_prefix(%s) → %d records", prefix, len(result))
        return result

    async def exists_with_prefix(self, prefix: str) -> bool:
        """Есть ли хотя бы один ключ с префиксом (ранний выход на первом совпадении)."""
        client = await self._active_client()
        pattern = _escape_glob(prefix) + "*"
        async for _ in client.scan_iter(match=pattern, count=_SCAN_COUNT):
            logger.debug("exists_with_prefix(%s) → True", prefix)
            return True
        logger.debug("exists_with_prefix(%s) → False", prefix)
        return False
