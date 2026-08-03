"""Загрузка расписания из выгрузки Excel в БД.

Расписание меняется раз в семестр, поэтому обновляется не планировщиком,
а вручную этой командой:

    python -m app.scripts.import_schedule

Путь можно не указывать: по умолчанию берётся выгрузка, лежащая в репозитории
(app/parser/schedule/uits.xlsx) — чтобы расписание воспроизводилось на любой
машине без ручного копирования файла. Свежий файл кладётся туда же поверх.

Таблица расписания заменяется целиком: файл выгрузки — единственный источник
правды. Данных рейтинга скрипт не касается.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.db.session import dispose_engine, init_models, session_scope
from app.logging_config import get_logger, setup_logging
from app.repository.schedule_repository import ScheduleRepository
from app.services.schedule_service import ScheduleService

log = get_logger(__name__)

# Выгрузка живёт в репозитории рядом с парсером: без неё расписание
# невоспроизводимо, а получить файл заново можно только в деканате.
DEFAULT_SOURCE = Path(__file__).resolve().parent.parent / "parser" / "schedule" / "uits.xlsx"


async def _run(path: Path) -> int:
    await init_models()
    try:
        async with session_scope() as session:
            service = ScheduleService(ScheduleRepository(session))
            count = await service.import_from_file(path)
            await session.commit()
        return count
    finally:
        await dispose_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузить расписание групп из файла Excel")
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=DEFAULT_SOURCE,
        help=f"путь к файлу выгрузки (.xlsx); по умолчанию {DEFAULT_SOURCE.name} из репозитория",
    )
    args = parser.parse_args()

    if not args.path.is_file():
        print(f"Файл не найден: {args.path}", file=sys.stderr)
        raise SystemExit(1)

    setup_logging()
    count = asyncio.run(_run(args.path))
    log.info("Done", groups=count)


if __name__ == "__main__":
    main()
