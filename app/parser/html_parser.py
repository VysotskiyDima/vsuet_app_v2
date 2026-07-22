"""Разбор HTML одной ведомости в целевые JSON-форматы.

Два формата записи (одна запись = один студент по одному предмету):
  * рейтинговый  — Зачёт/Экзамен с разбивкой по контрольным точкам (control_points);
  * оценочный    — остальные типы, а также Зачёт/Экзамен без КТ (поле grade).

Веса берутся из шапки таблицы (общие для группы), баллы — из строки студента.
Отсутствующие значения заменяются строкой "-".
"""

import re

from bs4 import BeautifulSoup

from app.entities.enums import RATING_VED_TYPES
from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import ControlPoint, RatingVedModel, SubjectScore
from app.logging_utils import get_logger




log = get_logger(__name__)





_PCT_RE = re.compile(r"^\d+%$")
_INT_RE = re.compile(r"^-?\d+$")

# Индексы ячеек строки студента (выверены по html-образцам ВГУИТ).
_ZACH_COL = 2          # «Номер зачетной книжки» — строго td[2]
_GRADE_COL = 4         # «Оценка» в оценочных таблицах
_RETAKE_COLS = (11, 9, 7)  # «Результат» 3-й/2-й/1-й пересдачи (поздний — приоритетнее)
_KT_FIRST_COL = 3      # первый балл КТ1 (Лек.); далее блоками по 5 ячеек на КТ




def _cell(tds: list, idx: int) -> str:
    """Текст ячейки по индексу либо "-", если ячейки нет или она пуста."""
    if idx < len(tds):
        text = tds[idx].get_text(strip=True)
        if text:
            return text
    return "-"


def _score(tds: list, idx: int) -> str | int:
    """Балл из ячейки: int, если число, иначе исходный текст либо "-"."""
    text = _cell(tds, idx)
    if text == "-":
        return "-"
    if _INT_RE.match(text):
        return int(text)
    return text


def _is_ved_row(row) -> bool:
    """Возвращает True, если строка таблицы является строкой с оценками студентов (содержит классы VedRow1 или VedRow2)."""
    classes = row.get("class") or []
    return "VedRow1" in classes or "VedRow2" in classes


def _pct_cells(row) -> list[int]:
    """Значения процентов из строки шапки в порядке следования."""
    out = []
    for td in row.find_all("td"):
        text = td.get_text(strip=True)
        if _PCT_RE.match(text):
            out.append(int(text[:-1]))
    return out


def _at(values: list[int], idx: int):
    """Безопасное извлечение значения из списка по индексу. Если индекс выходит за пределы, возвращает заглушку '-'."""
    return values[idx] if idx < len(values) else "-"


def _parse_header_weights(table) -> tuple[int, list[int], list[int]]:
    """Извлекает количество контрольных точек (КТ) и их веса из шапки таблицы ведомости.

    Возвращает кортеж из трех элементов:
      - количество контрольных точек (КТ) на основе столбцов «Итог по КТ»;
      - список весов каждой контрольной точки (КТ);
      - плоский список весов для каждого вида учебной работы (по 4 на каждую КТ: Лек., Пр., Лаб., Др.).
    """
    header_rows = [r for r in table.find_all("tr") if not _is_ved_row(r)]
    if not header_rows:
        return 0, [], []

    num_kt = sum(
        1
        for td in header_rows[0].find_all("td")
        if "Итог по КТ" in td.get_text()
    )

    kt_weights: list[int] = []
    work_weights: list[int] = []
    for row in header_rows[1:]:
        texts = [td.get_text(strip=True) for td in row.find_all("td")]
        if not any(t for t in texts):
            continue
        # Строка весов КТ: содержит метку «Вес Точки,%».
        if any("Вес Точки" in t for t in texts):
            kt_weights = _pct_cells(row)
        # Строка весов видов работ: только проценты (и пустые ячейки).
        elif all((not t) or _PCT_RE.match(t) for t in texts):
            work_weights = _pct_cells(row)

    return num_kt, kt_weights, work_weights


def _parse_rating(table, rows: list, ved_type: str, subject_name: str) -> list[RatingVedModel]:
    """Разбирает строки студентов в таблице рейтингового формата (с разбивкой по КТ и видам работ) и формирует список записей."""
    num_kt, _, work_weights = _parse_header_weights(table)

    records: list[RatingVedModel] = []
    for row in rows:
        tds = row.find_all("td")
        if not tds:
            continue

        control_points: list[ControlPoint] = []
        for i in range(num_kt):
            base = _KT_FIRST_COL + i * 5
            w = i * 4
            control_points.append(
                ControlPoint(
                    kt_num=i + 1,
                    lecture=SubjectScore(score=_score(tds, base), weight=_at(work_weights, w)),
                    practice=SubjectScore(score=_score(tds, base + 1), weight=_at(work_weights, w + 1)),
                    lab=SubjectScore(score=_score(tds, base + 2), weight=_at(work_weights, w + 2)),
                    other=SubjectScore(score=_score(tds, base + 3), weight=_at(work_weights, w + 3)),
                    total=_score(tds, base + 4),
                )
            )

        final_idx = _KT_FIRST_COL + num_kt * 5 + 1  # пропускаем колонку «Надбавка %»
        records.append(
            RatingVedModel(
                zach_number=_cell(tds, _ZACH_COL),
                subject_name=subject_name,
                ved_type=ved_type,
                control_points=control_points,
                final_rating=_score(tds, final_idx),
            )
        )
    return records


def _extract_grade(tds: list) -> str:
    """Оценка студента: приоритет — поздняя пересдача, затем основная оценка."""
    for idx in _RETAKE_COLS:
        value = _cell(tds, idx)
        if value != "-":
            return value
    return _cell(tds, _GRADE_COL)


def _parse_grade(rows: list, ved_type: str, subject_name: str) -> list[NotRatingVedModel]:
    """Разбирает строки студентов в таблице оценочного формата (где возвращается только одна финальная оценка) и формирует список записей."""
    records: list[NotRatingVedModel] = []
    for row in rows:
        tds = row.find_all("td")
        if not tds:
            continue
        records.append(
            NotRatingVedModel(
                zach_number=_cell(tds, _ZACH_COL),
                subject_name=subject_name,
                ved_type=ved_type,
                grade=_extract_grade(tds),
            )
        )
    return records


def parse_ved_html(html: str) -> list[RatingVedModel] | list[NotRatingVedModel]:
    """Разбирает HTML ведомости в список записей целевого формата.

    Возвращает пустой список для нерабочей ведомости (нет/пустой
    ucVedBox_lblTypeVed) — это штатная ситуация, не ошибка.
    """
    soup = BeautifulSoup(html, "lxml")

    type_tag = soup.find("span", id="ucVedBox_lblTypeVed")
    if not type_tag or not type_tag.get_text(strip=True):
        log.debug("Skip: no ucVedBox_lblTypeVed (non-functional vedomost)")
        return []

    ved_type = type_tag.get_text(strip=True)
    dis_tag = soup.find("span", id="ucVedBox_lblDis")
    subject_name = dis_tag.get_text(strip=True) if dis_tag and dis_tag.get_text(strip=True) else "-"

    rows = soup.find_all("tr", class_=["VedRow1", "VedRow2"])
    table = soup.find("table", id="ucVedBox_tblVed")

    has_kt = soup.find("input", id="ucVedBox_chkShowKT") is not None
    is_rating =ved_type in RATING_VED_TYPES and has_kt and table is not None

    fmt = "reitingoviy" if is_rating else "otsenochniy"
    log.debug("Parsing vedomost", type=ved_type, subject=subject_name, format=fmt, rows=len(rows))

    if is_rating:
        records = _parse_rating(table, rows, ved_type, subject_name)
    else:
        records = _parse_grade(rows, ved_type, subject_name)

    log.debug("Parsing result", records=len(records), type=ved_type, subject=subject_name)
    return records
