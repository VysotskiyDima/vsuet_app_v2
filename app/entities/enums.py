from enum import Enum


class VedType(str, Enum):
    """Название видов ведомостей с сайта ВГУИТ."""

    ZACHET = "Зачет"
    EKZAMEN = "Экзамен"
    VYPUSKNAYA_RABOTA = "Выпуская работа"  # «Выпуская работа» — без «н», это написание источника
    GOSEKZAMEN = "ГосЭкзамен"
    KONTROLNAYA_RABOTA = "Контрольная работа"
    KURSOVAYA_RABOTA = "Курсовая работа"
    KURSOVOY_PROEKT = "Курсовой проект"
    PRAKTIKA = "Практика"


RATING_VED_TYPES: frozenset[VedType] = frozenset(
    {
        VedType.ZACHET,
        VedType.EKZAMEN,
    }
)

NOT_RATING_VED_TYPES: frozenset[VedType] = frozenset(VedType) - RATING_VED_TYPES
