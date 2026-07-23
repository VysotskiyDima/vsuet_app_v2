from enum import Enum

from pydantic import BaseModel

from app.entities.enums import VedType


class Grade(str, Enum):
    """Сокращённые оценки, как приходят с сайта."""

    OTLICHNO = "Отл"
    HOROSHO = "Хор"
    UDOVLETVORITELNO = "Удовл"
    NEUDOVLETVORITELNO = "Неуд"
    ZACHTENO = "Зачтено"
    NE_ZACHTENO = "Не зачтено"


class NotRatingVedModel(BaseModel):
    zach_number: str
    subject_name: str
    ved_type: VedType
    grade: Grade | str  # т.к может прийти -
