"""Бизнес-логика чтения данных студента из активной БД."""

from fastapi import Request


from app.entities.student_exists_model import StudentExistsModel
from app.repository.redis_repository import RedisRepository


class StudentService:
    def __init__(self, repo: RedisRepository) -> None:
        self._repo = repo

    async def exists(self, zach_number: str) -> StudentExistsModel:
        """Есть ли в активной БД хотя бы одна запись студента."""
        exists = await self._repo.exists_with_prefix(f"{zach_number}:")
        result = StudentExistsModel(zach_number=zach_number, exists=exists)
        return result


def get_student_service(request: Request) -> StudentService:
    return request.app.state.student_service   
