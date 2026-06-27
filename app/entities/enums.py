from enum import Enum
from typing import Annotated

from pydantic import Field


class VedType(str, Enum):
    """Типы ведомостей ровно в том написании, в каком приходят с сайта.

    Значение участвует в ключе Redis и в сравнении типов — менять/нормализовать
    написание нельзя (в т.ч. «Выпуская работа» — без «к», это написание источника).
    """

    ZACHET = "Зачет"
    EKZAMEN = "Экзамен"
    VYPUSKNAYA_RABOTA = "Выпуская работа"
    GOSEKZAMEN = "ГосЭкзамен"
    KONTROLNAYA_RABOTA = "Контрольная работа"
    KURSOVAYA_RABOTA = "Курсовая работа"
    KURSOVOY_PROEKT = "Курсовой проект"
    PRAKTIKA = "Практика"


RATING_VED_TYPES: frozenset[VedType] = frozenset({
    VedType.ZACHET,
    VedType.EKZAMEN,
})

NOT_RATING_VED_TYPES: frozenset[VedType] = frozenset(VedType) - RATING_VED_TYPES
