"""Бизнес-логика чтения данных о студенте: наличие в снапшоте и его группа."""

from fastapi import Depends

from app.entities.student_exists_model import StudentExistsModel
from app.entities.student_group_model import StudentGroupModel
from app.repository.rating_repository import RatingRepository, get_rating_repository


class StudentService:
    def __init__(self, repo: RatingRepository) -> None:
        self._repo = repo

    async def exists(self, zach_number: str) -> StudentExistsModel:
        """Есть ли в снапшоте хотя бы одна запись студента."""
        exists = await self._repo.student_exists(zach_number)
        return StudentExistsModel(zach_number=zach_number, exists=exists)

    async def group(self, zach_number: str) -> StudentGroupModel:
        """Группа студента; None, если связка ещё не собрана."""
        group_name = await self._repo.get_group(zach_number)
        return StudentGroupModel(zach_number=zach_number, group_name=group_name)


def get_student_service(repo: RatingRepository = Depends(get_rating_repository)) -> StudentService:
    """Зависимость FastAPI: сервис поверх репозитория текущего запроса."""
    return StudentService(repo)
