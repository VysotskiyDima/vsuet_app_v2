"""Бизнес-логика чтения рейтинговых данных студента из активной БД."""

import logging

from fastapi import Request

from app.entities.enums import RATING_VED_TYPES, NOT_RATING_VED_TYPES, VedType
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.repository.redis_repository import RedisRepository

logger = logging.getLogger(__name__)


class RatingService:
    def __init__(self, repo: RedisRepository) -> None:
        self._repo = repo

    async def get_by_ved_type(
        self, zach_number: str, ved_type: VedType,
    ) -> list[RatingVedModel] | list[NotRatingVedModel]:
        """Записи студента заданного типа ведомости (всегда список, м.б. пустой)."""
        prefix = f"{zach_number}:{ved_type.value}:"
        records = await self._repo.get_by_prefix(prefix)
        logger.debug(
            "get_by_ved_type(%s, %s) → %d records",
            zach_number, ved_type.value, len(records),
        )

        if ved_type in RATING_VED_TYPES:
            return [RatingVedModel(**record) for record in records]
            
        if ved_type in NOT_RATING_VED_TYPES:
            return [NotRatingVedModel(**record) for record in records]


def get_rating_service(request: Request) -> RatingService:
    return request.app.state.rating_service
