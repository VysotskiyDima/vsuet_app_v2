"""Слой доступа к данным: расписание групп.

Как и остальные репозитории, сессию получает снаружи и сам подключений не
создаёт. Формат хранения (JSON в TEXT-колонке) наружу не протекает: наверх
уходит уже разобранный документ.
"""

import json

from fastapi import Depends
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GroupSchedule
from app.db.session import get_session
from app.logging_config import get_logger

log = get_logger(__name__)


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, group_name: str) -> dict | None:
        """Расписание группы; None, если для неё расписания нет."""
        raw = await self._session.scalar(select(GroupSchedule.schedule).where(GroupSchedule.group_name == group_name))
        log.debug("get_schedule", group=group_name, found=raw is not None)
        return json.loads(raw) if raw else None

    async def groups(self) -> list[str]:
        """Названия групп, для которых расписание загружено."""
        rows = await self._session.scalars(select(GroupSchedule.group_name).order_by(GroupSchedule.group_name))
        return list(rows)

    async def replace_all(self, schedules: dict[str, dict]) -> int:
        """Заменяет расписание целиком одной транзакцией.

        Файл выгрузки — единственный источник правды: группы, пропавшие из него,
        должны исчезнуть и здесь, поэтому таблица очищается перед заливкой.
        Коммит остаётся за вызывающим.
        """
        await self._session.execute(delete(GroupSchedule))
        if not schedules:
            return 0

        rows = [
            {"group_name": name, "schedule": json.dumps(schedule, ensure_ascii=False)}
            for name, schedule in schedules.items()
        ]
        await self._session.execute(insert(GroupSchedule), rows)
        log.debug("Schedules written", groups=len(rows))
        return len(rows)


def get_schedule_repository(session: AsyncSession = Depends(get_session)) -> ScheduleRepository:
    """Зависимость FastAPI: репозиторий поверх сессии текущего запроса."""
    return ScheduleRepository(session)
