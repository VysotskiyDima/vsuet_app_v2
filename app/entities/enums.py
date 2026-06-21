from enum import Enum


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


# Типы с рейтинговой (100-балльной) таблицей по контрольным точкам.
RATING_VED_TYPES = {VedType.ZACHET, VedType.EKZAMEN}


# Маппинг «человекочитаемый сегмент URL → точное значение ved_type».
# Латиница используется только в путях; в ключах Redis тип остаётся на русском.
URL_SEGMENT_TO_VED_TYPE: dict[str, VedType] = {
    "zachet": VedType.ZACHET,
    "ekzamen": VedType.EKZAMEN,
    "vypusknaya-rabota": VedType.VYPUSKNAYA_RABOTA,
    "gosekzamen": VedType.GOSEKZAMEN,
    "kontrolnaya-rabota": VedType.KONTROLNAYA_RABOTA,
    "kursovaya-rabota": VedType.KURSOVAYA_RABOTA,
    "kursovoy-proekt": VedType.KURSOVOY_PROEKT,
    "praktika": VedType.PRAKTIKA,
}


class Grade(str, Enum):
    """Сокращённые оценки, как приходят с сайта."""

    OTLICHNO = "Отл"
    HOROSHO = "Хор"
    UDOVLETVORITELNO = "Удовл"
    NEUDOVLETVORITELNO = "Неуд"
    ZACHTENO = "Зачтено"
    NE_ZACHTENO = "Не зачтено"
