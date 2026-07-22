"""Централизованная настройка логирования с поддержкой трассировки.

Формат: [время][уровень][трассировка][исполняемая строка] сообщение.
Уровень берётся из env-переменной LOG_LEVEL (по умолчанию INFO).
Здесь же живёт стартовый ASCII-баннер — визуальная часть вывода приложения;
все цвета (уровней, трассировки, градиента баннера) — в config.LoggingSettings.
"""

import contextvars
import logging
import os
import sys
from typing import Any, Dict

from app.config import settings

# Контекст для трассировочных идентификаторов (например, REQUEST-UUID, TRANSACTION-ID)
trace_ctx: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("trace_ctx", default={})

# Оформление (цвета ANSI) сгруппировано в config.LoggingSettings.
_STYLE = settings.logging


class CustomFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        # Форматируем время с добавлением миллисекунд (через запятую)
        t = self.formatTime(record, self.datefmt)
        asctime_ms = f"{t},{int(record.msecs):03d}"
        asctime_ms_str = f"{_STYLE.time_color}{asctime_ms}{_STYLE.reset}"

        levelname = record.levelname
        color = _STYLE.level_colors.get(levelname, "")
        levelname_str = f"{color}{levelname}{_STYLE.reset}" if color else levelname

        # Определяем путь к файлу относительно корня проекта
        pathname = record.pathname
        cwd = os.getcwd()
        if pathname.startswith(cwd):
            exec_line = os.path.relpath(pathname, cwd)
        else:
            # Для внешних библиотек убираем ведущий слэш, чтобы получить вид "usr/local/..."
            exec_line = pathname.lstrip(os.sep)

        exec_str = f"{exec_line}:{record.lineno}"

        # Добавляем данные трассировки, если они установлены в контексте
        ctx = trace_ctx.get()
        ctx_str = ""
        if ctx:
            ctx_content = "".join(f"[{k}={v}]" for k, v in ctx.items())
            ctx_str = f"{_STYLE.ctx_color}{ctx_content}{_STYLE.reset}"

        message = record.getMessage()
        log_line = f"[{asctime_ms_str}][{levelname_str}]{ctx_str}[{exec_str}] {message}"

        # Обработка исключений и трассировки стека
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if log_line[-1:] != "\n":
                log_line += "\n"
            log_line += record.exc_text

        if record.stack_info:
            if log_line[-1:] != "\n":
                log_line += "\n"
            log_line += self.formatStack(record.stack_info)

        return log_line


def print_banner() -> None:
    """Печатает resources/rating_v2.txt с диагональным градиентом (см. banner_colors)."""
    banner_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "rating_v2.txt")
    if not os.path.exists(banner_path):
        return
    try:
        with open(banner_path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if not lines:
            return

        colors = _STYLE.banner_colors
        max_w = max(len(line) for line in lines)
        max_h = len(lines)
        diagonal_coeff = 4.0
        max_val = (max_w - 1) + (max_h - 1) * diagonal_coeff

        def gradient_color(t: float) -> tuple[int, int, int]:
            t = max(0.0, min(1.0, t))
            if t >= 1.0:
                return colors[-1]
            segment_size = 1.0 / (len(colors) - 1)
            segment_idx = int(t // segment_size)
            local_t = (t - (segment_idx * segment_size)) / segment_size
            c1, c2 = colors[segment_idx], colors[segment_idx + 1]
            return tuple(int(a + (b - a) * local_t) for a, b in zip(c1, c2))

        colored_lines = []
        for row_idx, line in enumerate(lines):
            colored_chars = []
            for col_idx, char in enumerate(line):
                if char.isspace():
                    colored_chars.append(char)
                else:
                    t = (col_idx + row_idx * diagonal_coeff) / max_val if max_val > 0 else 0
                    r, g, b = gradient_color(t)
                    colored_chars.append(f"\033[38;2;{r};{g};{b}m{char}{_STYLE.reset}")
            colored_lines.append("".join(colored_chars))

        sys.stdout.write("\n".join(colored_lines) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def setup_logging() -> None:
    """Инициализирует логирование всего приложения. Вызывать один раз при старте."""
    # Уровень нормализован валидатором LoggingSettings (легаси-алиас DEV → INFO).
    level = getattr(logging, settings.logging.level)

    root = logging.getLogger()
    root.setLevel(level)

    # Убираем дублирование, если setup вызывается повторно
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(CustomFormatter())
    root.addHandler(handler)

    # Приглушаем болтливые библиотеки до WARNING, чтобы не засорять вывод
    for noisy in ("httpx", "httpcore", "asyncio", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Перенаправляем системные логи uvicorn в наш кастомный формат и убираем дубли
    for name in ("uvicorn", "uvicorn.error"):
        logger_uni = logging.getLogger(name)
        logger_uni.handlers.clear()
        logger_uni.propagate = True

    # Приглушаем логи доступа uvicorn, так как мы пишем логи запросов в роутерах
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

