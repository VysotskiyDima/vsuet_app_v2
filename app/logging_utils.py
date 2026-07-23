"""Структурированное логирование: единая точка формата «сообщение | k=v».

Сознательно НЕ кастомный Logger-класс: подмена logging.Logger теряет ленивую
интерполяцию, ломает %(pathname)s/%(lineno)d (указывали бы на обёртку), а
сторонние библиотеки всё равно пишут через stdlib. Вместо этого — LoggerAdapter:
кадры модуля logging пропускаются при поиске вызывающего, поэтому file:line
в логах остаются честными, а данные передаются полями, а не вклеиваются
вручную в текст по всему проекту.

Использование:
    from app.logging_utils import get_logger

    log = get_logger(__name__)
    log.info("Stage 2 completed", groups=5, links=1200, duration_s=1.3)
    # → [..][INFO][app/...:42] Stage 2 completed  |  groups=5  links=1200  duration_s=1.3

Служебные kwargs logging (exc_info, stacklevel, extra, stack_info) проходят
насквозь и полями не считаются.
"""

import logging
from collections.abc import MutableMapping
from typing import Any

_LOGGING_KWARGS = frozenset({"exc_info", "stack_info", "stacklevel", "extra"})


class KVLogger(logging.LoggerAdapter):
    """Адаптер: произвольные kwargs становятся полями «k=v» в конце сообщения."""

    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> tuple[Any, MutableMapping[str, Any]]:
        fields = {k: kwargs.pop(k) for k in list(kwargs) if k not in _LOGGING_KWARGS}
        if fields:
            msg = f"{msg}  |  " + "  ".join(f"{k}={v}" for k, v in fields.items())
        return msg, kwargs


def get_logger(name: str) -> KVLogger:
    return KVLogger(logging.getLogger(name), {})
