from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = SettingsConfigDict(env_file=".env", extra="ignore")


class ParsingSettings(BaseSettings):
    """Период парсинга. Меняется вручную раз в полгода при смене семестра."""

    model_config = {**_ENV, "env_prefix": "PARSING_"}

    year: str
    semester: str


class DatabaseSettings(BaseSettings):
    """SQLite: путь до файла БД и параметры соединения.

    Путь — переменная окружения: в контейнере это примонтированный том,
    при локальной отладке — файл рядом с проектом.
    """

    model_config = {**_ENV, "env_prefix": "DB_"}

    path: str = "data/rating.sqlite3"
    # Сколько читатель ждёт освобождения блокировки, прежде чем упасть с
    # SQLITE_BUSY. Цикл парсинга держит запись долго, но в режиме WAL читателей
    # он не блокирует — таймаут нужен лишь на короткие моменты чекпоинта.
    busy_timeout_ms: int = 5000
    # Размер батча при заливке снапшота: компромисс между числом executemany
    # и объёмом удерживаемых в памяти строк.
    write_batch_size: int = 2000
    # Пул подключений: читатели запросов плюс одно длительное подключение
    # писателя, удерживаемое на весь цикл парсинга.
    pool_size: int = 5
    max_overflow: int = 5


class SchedulerSettings(BaseSettings):
    """Интервал запуска цикла парсинга, минуты."""

    model_config = {**_ENV, "env_prefix": "SCHEDULER_"}

    interval_minutes: int = 30


class RatingSiteSettings(BaseSettings):
    """URL-ы и кодировка сайта рейтинга ВГУИТ."""

    model_config = {**_ENV, "env_prefix": "RATING_"}

    base_url: str = "https://rating.vsuet.ru/web/ved/Default.aspx"
    ved_url: str = "https://rating.vsuet.ru/web/ved/Ved.aspx"
    encoding: str = "windows-1251"


class HtmlFormSettings(BaseModel):
    """Имена ASP.NET-контролов формы Default.aspx (разметка сайта)."""

    faculty_select: str = "ctl00$ContentPage$cmbFacultets"
    group_select: str = "ctl00$ContentPage$cmbGroups"
    years_select: str = "ctl00$ContentPage$cmbYears"
    semester_select: str = "ctl00$ContentPage$cmbSem"
    grid_id_pattern: str = "Grid"  # id таблицы со ссылками на ведомости


class ScraperSettings(BaseModel):
    """Тюнинг обхода rating.vsuet.ru.

    Значения подобраны замерами против слабого сервера ВГУИТ — это свойства
    кода, а не окружения, поэтому в .env они не выносятся.
    """

    concurrency: int = 12
    timeout_s: float = 30.0
    retries: int = 4
    retry_backoff_s: float = 2.0  # база экспоненциального бэкоффа
    retry_max_delay_s: float = 20.0
    user_agent: str = "Mozilla/5.0"


class HtmlVedSettings(BaseModel):
    """Разметка HTML-ведомости: индексы колонок и маркеры.

    Выверено по html-образцам ВГУИТ; при дрейфе вёрстки сайта правится здесь.
    """

    zach_col: int = 2  # «Номер зачетной книжки» — строго td[2]
    grade_col: int = 4  # «Оценка» в оценочных таблицах
    retake_cols: tuple[int, ...] = (11, 9, 7)  # «Результат» 3-й/2-й/1-й пересдачи (поздняя — приоритетнее)
    kt_first_col: int = 3  # первый балл КТ1 (Лек.)
    kt_block_cells: int = 5  # ячеек на одну КТ: Лек/Пр/Лаб/Др/Итог
    kt_works: int = 4  # видов работ в КТ: Лек/Пр/Лаб/Др
    final_rating_offset: int = 1  # пропуск колонки «Надбавка %» перед итогом

    type_span_id: str = "ucVedBox_lblTypeVed"
    subject_span_id: str = "ucVedBox_lblDis"
    table_id: str = "ucVedBox_tblVed"
    kt_checkbox_id: str = "ucVedBox_chkShowKT"
    row_classes: tuple[str, ...] = ("VedRow1", "VedRow2")
    kt_total_marker: str = "Итог по КТ"
    kt_weight_marker: str = "Вес Точки"


class LoggingSettings(BaseSettings):
    """Логирование: уровень — из окружения (LOG_LEVEL), оформление — только здесь."""

    model_config = {**_ENV, "env_prefix": "LOG_"}

    level: str = "INFO"

    reset: str = "\033[0m"
    time_color: str = "\033[94m"
    level_colors: dict[str, str] = Field(
        default_factory=lambda: {
            "DEBUG": "\033[90m",
            "INFO": "\033[32m",
            "WARNING": "\033[33m",
            "ERROR": "\033[31m",
            "CRITICAL": "\033[1;31m",
        }
    )
    banner_colors: tuple[tuple[int, int, int], ...] = ((234, 88, 12), (249, 115, 22), (251, 191, 36))

    @field_validator("level", mode="before")
    @classmethod
    def validate_level(cls, v: str) -> str:
        val = str(v).strip().upper()
        if val not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("LOG_LEVEL must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL")
        return val


class Settings(BaseModel):
    parsing: ParsingSettings = Field(default_factory=ParsingSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    site: RatingSiteSettings = Field(default_factory=RatingSiteSettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    html_ved: HtmlVedSettings = Field(default_factory=HtmlVedSettings)
    html_form: HtmlFormSettings = Field(default_factory=HtmlFormSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
