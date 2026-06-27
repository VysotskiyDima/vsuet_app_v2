from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Период парсинга. Меняется вручную раз в полгода при смене семестра.
    parsing_year: str
    parsing_semester: str

    # Redis. Две логические БД под данные (активная/фоновая меняются ролями)
    # и отдельная служебная БД под указатель активной БД.
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db_0: int = 0
    redis_db_1: int = 1
    redis_meta_db: int = 2

    # Интервал запуска планировщика парсинга, минуты.
    scheduler_interval_minutes: int = 30

    # URL-ы сайта рейтинга ВГУИТ.
    rating_base_url: str = "https://rating.vsuet.ru/web/ved/Default.aspx"
    rating_ved_url: str = "https://rating.vsuet.ru/web/ved/Ved.aspx"

    # Уровень логирования (DEBUG / DEV).
    log_level: str = "DEV"

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        if not isinstance(v, str):
            return "DEV"
        val = v.strip().upper()
        if val not in ("DEBUG", "DEV"):
            raise ValueError("log_level must be either DEBUG or DEV")
        return val


settings = Settings()

