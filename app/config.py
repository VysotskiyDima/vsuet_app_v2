"""Конфигурация приложения: все настройки сгруппированы по подсистемам.

Принцип разделения:
  * в .env выносится только то, что меняется между окружениями/контейнерами —
    адреса сервисов, период парсинга, интервал планировщика, уровень логов;
  * тюнинг кода (колонки HTML-ведомости, тайминги HTTP, цвета логов) живёт
    здесь как дефолты соответствующих групп и в .env не дублируется.

Группы, читающие окружение, наследуют BaseSettings и держат свой env_prefix
(имена переменных совпадают с историческими: REDIS_HOST, PARSING_YEAR, ...).
Чисто кодовые группы — обычные BaseModel без чтения окружения.
"""

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = SettingsConfigDict(env_file=".env", extra="ignore")


class ParsingSettings(BaseSettings):
    """Период парсинга. Меняется вручную раз в полгода при смене семестра."""

    model_config = {**_ENV, "env_prefix": "PARSING_"}

    year: str
    semester: str


class RedisSettings(BaseSettings):
    """Redis: две логические БД под данные (активная/фоновая меняются ролями)
    и отдельная служебная БД под указатель активной БД."""

    model_config = {**_ENV, "env_prefix": "REDIS_"}

    host: str = "redis"
    port: int = 6379
    db_0: int = 0
    db_1: int = 1
    meta_db: int = 2


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

    concurrency: int = 12  # лучшее значение по итогам тестов; сервер сериализует
    # запросы одной ASP.NET-сессии, поэтому конкурентность
    # работает только вместе с пулом клиентов
    timeout_s: float = 30.0  # connect/read/write/pool; connect < 30 с ловил
    # штормы ConnectTimeout на всплесках очереди SYN
    retries: int = 4  # запас попыток, чтобы потери ведомостей были < 1%
    retry_backoff_s: float = 2.0  # база экспоненциального бэкоффа
    retry_max_delay_s: float = 20.0  # потолок задержки между попытками
    user_agent: str = "Mozilla/5.0"


class HtmlVedSettings(BaseModel):
    """Разметка HTML-ведомости: индексы колонок и маркеры.

    Выверено по html-образцам ВГУИТ; при дрейфе вёрстки сайта правится здесь.
    """

    zach_col: int = 2  # «Номер зачетной книжки» — строго td[2]
    grade_col: int = 4  # «Оценка» в оценочных таблицах
    retake_cols: tuple[int, ...] = (11, 9, 7)  # «Результат» 3-й/2-й/1-й пересдачи
    # (поздняя — приоритетнее)
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
    time_color: str = "\033[94m"  # Blue
    ctx_color: str = "\033[36m"  # Cyan
    level_colors: dict[str, str] = Field(
        default_factory=lambda: {
            "DEBUG": "\033[90m",  # Grey
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[1;31m",  # Bold Red
        }
    )
    # Градиент ASCII-баннера при старте: Indigo → Violet → Pink.
    banner_colors: tuple[tuple[int, int, int], ...] = ((79, 70, 229), (147, 51, 234), (236, 72, 153))

    @field_validator("level", mode="before")
    @classmethod
    def validate_level(cls, v: str) -> str:
        val = str(v).strip().upper()
        if val == "DEV":  # легаси-алиас старой схемы «DEBUG / DEV»
            return "INFO"
        if val not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError("LOG_LEVEL must be one of DEBUG/INFO/WARNING/ERROR/CRITICAL")
        return val


class Settings(BaseModel):
    parsing: ParsingSettings = Field(default_factory=ParsingSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    scheduler: SchedulerSettings = Field(default_factory=SchedulerSettings)
    site: RatingSiteSettings = Field(default_factory=RatingSiteSettings)
    scraper: ScraperSettings = Field(default_factory=ScraperSettings)
    html_ved: HtmlVedSettings = Field(default_factory=HtmlVedSettings)
    html_form: HtmlFormSettings = Field(default_factory=HtmlFormSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


settings = Settings()
