"""Бизнес-логика чтения данных студента из активной БД."""

import logging

from app.entities.enums import VedType
from app.repository.redis_repository import RedisRepository

logger = logging.getLogger(__name__)


class StudentService:
    def __init__(self, repo: RedisRepository) -> None:
        self._repo = repo

    async def exists(self, zach_number: str) -> bool:
        """Есть ли в активной БД хотя бы одна запись студента."""
        result = await self._repo.exists_with_prefix(f"{zach_number}:")
        logger.debug("exists(%s) → %s", zach_number, result)
        return result

    async def get_by_ved_type(self, zach_number: str, ved_type: VedType) -> list[dict]:
        """Записи студента заданного типа ведомости (всегда список, м.б. пустой)."""
        prefix = f"{zach_number}:{ved_type.value}:"
        records = await self._repo.get_by_prefix(prefix)
        logger.debug(
            "get_by_ved_type(%s, %s) → %d records", zach_number, ved_type.value, len(records)
        )
        return records
