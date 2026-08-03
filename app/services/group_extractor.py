"""Извлечение связки «номер зачётки → название группы».

Отдельного обхода сайта для этого не нужно: ParserService.collect_ved_links()
уже возвращает ссылки, сгруппированные по названию группы, а записи внутри
каждой ведомости содержат номер зачётки. Значит группа известна для каждой
разобранной ведомости, и связку достаточно накопить по ходу того же цикла —
ни одного дополнительного запроса к rating.vsuet.ru.

Экстрактор ничего не знает ни о сети, ни о БД: на вход — группа и записи её
ведомости, на выход — готовые пары для записи в снапшот.
"""

from collections import Counter, defaultdict
from collections.abc import Sequence

from app.entities.not_rating_ved_model import NotRatingVedModel
from app.entities.rating_ved_model import RatingVedModel
from app.logging_config import get_logger

log = get_logger(__name__)

VedRecord = RatingVedModel | NotRatingVedModel

# Парсер подставляет прочерк в пустую ячейку, поэтому строки без номера
# зачётки приходят с «-». Это служебные строки ведомости, а не студенты:
# без фильтра они слипаются в одного фантомного студента с номером «-».
_BLANK_ZACH = {"", "-"}


class GroupExtractor:
    """Накопитель связок «зачётка → группа».

    Один студент встречается во всех ведомостях своей группы, поэтому одна и та
    же пара приходит многократно — это норма.

    Сложнее случай, когда зачётка приходит с разными группами: так бывает при
    переводе студента (на сайте остались ведомости обеих групп) и на общих
    ведомостях, которые сайт показывает сразу нескольким группам. Побеждает та
    группа, в ведомостях которой студент встретился чаще; при равенстве —
    первая по алфавиту.

    Важно, что правило детерминированное: ведомости разбираются конкурентно, и
    вариант «побеждает последняя» давал бы студенту разную группу от цикла к
    циклу, то есть прыгающее значение в профиле.
    """

    def __init__(self) -> None:
        self._seen: dict[str, Counter[str]] = defaultdict(Counter)
        self.skipped_blank = 0

    def feed(self, group_name: str, records: Sequence[VedRecord]) -> None:
        """Скармливает записи одной ведомости, зная её группу.

        На вход идут ровно те модели, что вернул parse_ved_html.
        """
        if not group_name:
            return
        for rec in records:
            zach = (rec.zach_number or "").strip()
            if zach in _BLANK_ZACH:
                self.skipped_blank += 1
                continue
            self._seen[zach][group_name] += 1

    def pairs(self) -> list[tuple[str, str]]:
        """Пары (номер зачётки, название группы) для записи в снапшот."""
        return [(zach, self._pick(counter)) for zach, counter in self._seen.items()]

    @staticmethod
    def _pick(counter: Counter[str]) -> str:
        """Самая частая группа; при равенстве — первая по алфавиту."""
        return min(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0]

    @property
    def students(self) -> int:
        return len(self._seen)

    @property
    def groups(self) -> int:
        return len({self._pick(c) for c in self._seen.values()})

    @property
    def ambiguous(self) -> int:
        """Сколько студентов встретились более чем в одной группе."""
        return sum(1 for c in self._seen.values() if len(c) > 1)
