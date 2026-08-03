"""Бизнес-логика чтения рейтинговых данных студента."""

from fastapi import Depends

from app.entities.enums import VedType
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.logging_config import get_logger
from app.repository.rating_repository import RatingRepository, get_rating_repository

log = get_logger(__name__)

VedRecord = RatingVedModel | NotRatingVedModel


class RatingService:
    def __init__(self, repo: RatingRepository) -> None:
        self._repo = repo

    async def get_by_ved_type(self, zach_number: str, ved_type: VedType) -> list[VedRecord]:
        """Записи студента заданного типа ведомости (всегда список, м.б. пустой).

        Модель выбирается по форме самой записи, а не по виду ведомости: парсер
        относит зачёт или экзамен без колонок КТ к оценочному формату, поэтому
        в одном разделе могут оказаться записи обеих форм.
        """
        records = await self._repo.get_records(zach_number, ved_type)
        log.debug(
            "get_by_ved_type",
            zach_number=zach_number,
            ved_type=ved_type.value,
            records=len(records),
        )
        return [
            RatingVedModel(**record) if "control_points" in record else NotRatingVedModel(**record)
            for record in records
        ]


def get_rating_service(repo: RatingRepository = Depends(get_rating_repository)) -> RatingService:
    """Зависимость FastAPI: сервис поверх репозитория текущего запроса."""
    return RatingService(repo)
