"""Слой доступа к данным: перезапись снапшота одной транзакцией.

Это то, что раньше делал blue-green swap на двух БД Redis с указателем в
третьей. Здесь достаточно транзакции: в режиме WAL читатели до коммита видят
прежние данные, а обрыв процесса посреди цикла откатывается движком. Отдельные
этапы «очистить фоновую БД» и «переключить активную» стали не нужны.

Сессия приходит снаружи (session_scope в планировщике) и живёт весь цикл —
несколько минут. Поэтому у писателя своя сессия, отдельная от тех, что
обслуживают запросы: иначе читающий запрос попал бы внутрь незавершённой
транзакции и увидел полузаписанный снапшот.
"""

import asyncio
import json
from collections.abc import Iterable, Sequence
from enum import Enum

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import SNAPSHOT_MODELS, GradeRecord, RatingRecord, StudentGroup
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.logging_config import get_logger

log = get_logger(__name__)

# Парсер отдаёт готовые доменные модели, а не словари (см. parse_ved_html).
VedRecord = RatingVedModel | NotRatingVedModel

# Прочерк — то, что парсер подставляет в пустую ячейку. Строки без номера
# зачётки это служебные строки ведомости, а не студенты: сохранённые, они
# слипаются в одного фантомного студента с номером «-», у которого «есть»
# записи из разных групп.
_BLANK_ZACH = {"", "-"}


def _as_text(value) -> str | None:
    """Значение в текст для хранения (см. app/db/models.py).

    Enum разворачиваем через .value: у str-Enum в Python 3.12 str(member) даёт
    «VedType.ZACHET», а не «Зачет», и в БД поехали бы имена членов вместо значений.
    """
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


class SnapshotRepository:
    """Перезапись снапшота в границах одной транзакции.

    Вызовы add_* сериализуются замком: пайплайн разбирает ведомости конкурентно,
    а сессия SQLAlchemy для параллельного использования не предназначена.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._lock = asyncio.Lock()
        self.rating_rows = 0
        self.grade_rows = 0
        self.group_rows = 0
        self.skipped_rows = 0  # строки без номера зачётки

    async def begin(self) -> None:
        """Открывает транзакцию и очищает таблицы снапшота."""
        for model in SNAPSHOT_MODELS:
            await self._session.execute(delete(model))
        log.debug("Snapshot transaction opened")

    async def add_records(self, records: Sequence[VedRecord]) -> None:
        """Записи одной ведомости: раскладываются по таблицам по форме записи."""
        if not records:
            return

        rating_rows: list[dict] = []
        grade_rows: list[dict] = []
        for rec in records:
            zach = (rec.zach_number or "").strip()
            if zach in _BLANK_ZACH:
                self.skipped_rows += 1
                continue
            common = {
                "zach_number": zach,
                "ved_type": _as_text(rec.ved_type),
                "subject_name": rec.subject_name,
            }
            # Ветвимся по фактическому типу модели, а НЕ по виду ведомости:
            # парсер выбирает форму по наличию колонок КТ, поэтому зачёт или
            # экзамен без контрольных точек приходит оценочной записью
            # (см. is_rating в app/parser/html_parser.py).
            if isinstance(rec, RatingVedModel):
                points = [cp.model_dump() for cp in rec.control_points]
                rating_rows.append(
                    {
                        **common,
                        "final_rating": _as_text(rec.final_rating),
                        "control_points": json.dumps(points, ensure_ascii=False),
                    }
                )
            else:
                grade_rows.append({**common, "grade": _as_text(rec.grade)})

        async with self._lock:
            if rating_rows:
                await self._insert(RatingRecord, rating_rows)
                self.rating_rows += len(rating_rows)
            if grade_rows:
                await self._insert(GradeRecord, grade_rows)
                self.grade_rows += len(grade_rows)

    async def add_groups(self, mapping: Iterable[tuple[str, str]]) -> None:
        """Пары (номер зачётки, название группы)."""
        rows = [{"zach_number": zach, "group_name": group} for zach, group in mapping]
        if not rows:
            return
        async with self._lock:
            await self._insert(StudentGroup, rows)
            self.group_rows += len(rows)

    async def _insert(self, model, rows: list[dict]) -> None:
        """Пакетная вставка с перезаписью совпавших ключей.

        OR REPLACE, потому что один и тот же студент с одним предметом может
        встретиться в двух ведомостях (пересдачи, общие ведомости).
        """
        stmt = insert(model).prefix_with("OR REPLACE")
        batch = settings.db.write_batch_size
        for start in range(0, len(rows), batch):
            await self._session.execute(stmt, rows[start : start + batch])

    async def commit(self) -> None:
        await self._session.commit()
        log.debug(
            "Snapshot committed",
            rating_rows=self.rating_rows,
            grade_rows=self.grade_rows,
            group_rows=self.group_rows,
        )

    async def rollback(self) -> None:
        await self._session.rollback()
        log.warning("Snapshot rolled back — прежние данные остались на месте")
