"""ORM-модели снапшота — единственное описание структуры таблиц.

Данные представляют собой снимок сайта рейтинга, целиком заменяемый каждым
циклом парсинга. Ключевые решения по схеме:

* Две таблицы под записи вместо одной с nullable-колонками: рейтинговые
  ведомости несут контрольные точки, оценочные — только итоговую оценку.
  Форму выбирает не вид ведомости, а наличие колонок КТ в источнике
  (см. is_rating в app/parser/html_parser.py), поэтому зачёт может оказаться
  и в той, и в другой таблице.

* control_points хранится одним JSON-полем, а не отдельной таблицей.
  Контрольные точки всегда читаются целиком вместе со своей записью и по
  отдельности не запрашиваются, поэтому нормализация дала бы соединение на
  каждый показ рейтинга без выигрыша. Понадобится выборка по КТ — в SQLite
  есть json_extract, схему менять не придётся.

* Составной первичный ключ (zach_number, ved_type, subject_name) заодно
  работает индексом основного запроса «записи студента по виду ведомости»:
  два первых поля — его левый префикс.

* Числовые по смыслу поля (final_rating, grade) объявлены текстом: источник
  присылает в них и числа, и прочерк «-», и словесные оценки. Приведение
  к нужному типу делает pydantic на выходе из сервиса.
"""

from sqlalchemy import Index, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Общая база моделей; от неё же берётся metadata для создания таблиц."""


class RatingRecord(Base):
    """Ведомость с контрольными точками (обычно зачёт или экзамен)."""

    __tablename__ = "rating_record"

    zach_number: Mapped[str] = mapped_column(Text, primary_key=True)
    ved_type: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_name: Mapped[str] = mapped_column(Text, primary_key=True)
    final_rating: Mapped[str | None] = mapped_column(Text)
    control_points: Mapped[str] = mapped_column(Text, nullable=False)


class GradeRecord(Base):
    """Ведомость без контрольных точек — только итоговая оценка."""

    __tablename__ = "grade_record"

    zach_number: Mapped[str] = mapped_column(Text, primary_key=True)
    ved_type: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_name: Mapped[str] = mapped_column(Text, primary_key=True)
    grade: Mapped[str | None] = mapped_column(Text)


class StudentGroup(Base):
    """Связка «зачётка → группа».

    Выводится из того же обхода, что и рейтинг: ссылки на ведомости собираются
    по группам, а номера зачёток есть в самих записях
    (см. app/services/group_extractor.py).
    """

    __tablename__ = "student_group"

    zach_number: Mapped[str] = mapped_column(Text, primary_key=True)
    group_name: Mapped[str] = mapped_column(Text, nullable=False)

    # Обратный разрез «кто в группе» — понадобится расписанию.
    __table_args__ = (Index("idx_student_group_name", "group_name"),)


class GroupSchedule(Base):
    """Расписание группы одним JSON-документом.

    Живёт отдельно от снапшота рейтинга: источник другой (выгрузка Excel),
    и обновляется вручную раз в семестр, а не каждые полчаса. Поэтому цикл
    парсинга эту таблицу не чистит.

    Документ хранится целиком, а не разложенным по строкам «занятие»: расписание
    группы всегда читается и заменяется целиком, выборок по отдельной паре нет.
    Структура описана в app/parser/schedule_parser.py.
    """

    __tablename__ = "group_schedule"

    group_name: Mapped[str] = mapped_column(Text, primary_key=True)
    schedule: Mapped[str] = mapped_column(Text, nullable=False)


# Таблицы снапшота рейтинга в порядке очистки перед заливкой нового цикла.
# Расписание сюда намеренно не входит — у него свой цикл обновления.
SNAPSHOT_MODELS = (RatingRecord, GradeRecord, StudentGroup)
