"""Бизнес-логика расписания: чтение по группе и загрузка из файла выгрузки."""

from pathlib import Path

from fastapi import Depends

from app.logging_config import get_logger
from app.parser.schedule_parser import parse_schedule
from app.repository.schedule_repository import ScheduleRepository, get_schedule_repository

log = get_logger(__name__)


class ScheduleService:
    def __init__(self, repo: ScheduleRepository) -> None:
        self._repo = repo

    async def for_group(self, group_name: str) -> dict | None:
        """Расписание группы; None, если оно ещё не загружено."""
        return await self._repo.get(group_name)

    async def groups(self) -> list[str]:
        return await self._repo.groups()

    async def import_from_file(self, path: str | Path) -> int:
        """Разбирает выгрузку и полностью заменяет расписание в БД.

        Возвращает число загруженных групп. Коммит остаётся за вызывающим:
        решение о фиксации принимает тот, кто владеет сессией.
        """
        schedules = parse_schedule(path)
        count = await self._repo.replace_all(schedules)
        log.info("Schedule imported", groups=count, source=str(path))
        return count


def get_schedule_service(repo: ScheduleRepository = Depends(get_schedule_repository)) -> ScheduleService:
    """Зависимость FastAPI: сервис поверх репозитория текущего запроса."""
    return ScheduleService(repo)
