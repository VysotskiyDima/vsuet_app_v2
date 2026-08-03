"""Слой доступа к данным: чтение снапшота.

Репозиторий не создаёт подключений — сессию ему отдают снаружи: в запросах её
подставляет зависимость get_session, в фоновом коде — session_scope. Благодаря
этому один и тот же класс работает и в API, и в цикле парсинга.

Наружу отдаются простые dict, сборку доменных моделей делает слой сервисов:
форму записи определяет не вид ведомости, а наличие контрольных точек, и решать
это должен тот, кто знает про модели.
"""

import json

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GradeRecord, RatingRecord, StudentGroup
from app.db.session import get_session
from app.entities.enums import VedType
from app.logging_config import get_logger

log = get_logger(__name__)


class RatingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_records(self, zach_number: str, ved_type: VedType) -> list[dict]:
        """Записи студента по виду ведомости в форме, готовой для моделей.

        Смотрим обе таблицы: один и тот же вид ведомости может дать записи любой
        формы — зачёт с контрольными точками попадёт в rating_record, а зачёт
        без них в grade_record. Различить их вызывающий может по наличию ключа
        control_points.
        """
        rating_rows = (
            await self._session.execute(
                select(RatingRecord).where(
                    RatingRecord.zach_number == zach_number,
                    RatingRecord.ved_type == ved_type.value,
                )
            )
        ).scalars()

        grade_rows = (
            await self._session.execute(
                select(GradeRecord).where(
                    GradeRecord.zach_number == zach_number,
                    GradeRecord.ved_type == ved_type.value,
                )
            )
        ).scalars()

        records: list[dict] = [
            {
                "zach_number": row.zach_number,
                "ved_type": row.ved_type,
                "subject_name": row.subject_name,
                "final_rating": row.final_rating,
                # Формат хранения (JSON в TEXT-колонке) наружу не протекает:
                # сервис получает уже готовый список контрольных точек.
                "control_points": json.loads(row.control_points),
            }
            for row in rating_rows
        ]
        records += [
            {
                "zach_number": row.zach_number,
                "ved_type": row.ved_type,
                "subject_name": row.subject_name,
                "grade": row.grade,
            }
            for row in grade_rows
        ]

        records.sort(key=lambda r: r["subject_name"])
        log.debug("get_records", zach_number=zach_number, ved_type=ved_type.value, records=len(records))
        return records

    async def student_exists(self, zach_number: str) -> bool:
        """Есть ли у студента хоть одна запись в снапшоте."""
        rating = select(RatingRecord.zach_number).where(RatingRecord.zach_number == zach_number)
        grade = select(GradeRecord.zach_number).where(GradeRecord.zach_number == zach_number)
        found = (await self._session.execute(rating.union_all(grade).limit(1))).first()
        exists = found is not None
        log.debug("student_exists", zach_number=zach_number, exists=exists)
        return exists

    async def get_group(self, zach_number: str) -> str | None:
        """Группа студента; None, если связки нет."""
        group = await self._session.scalar(
            select(StudentGroup.group_name).where(StudentGroup.zach_number == zach_number)
        )
        log.debug("get_group", zach_number=zach_number, group=group)
        return group

    async def counts(self) -> dict[str, int]:
        """Число строк в таблицах снапшота — для логов и отчёта цикла."""
        result: dict[str, int] = {}
        for model in (RatingRecord, GradeRecord, StudentGroup):
            total = await self._session.scalar(select(func.count()).select_from(model))
            result[model.__tablename__] = int(total or 0)
        return result


def get_rating_repository(session: AsyncSession = Depends(get_session)) -> RatingRepository:
    """Зависимость FastAPI: репозиторий поверх сессии текущего запроса."""
    return RatingRepository(session)
