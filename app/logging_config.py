"""Централизованная настройка логирования с поддержкой трассировки.

Формат: [время][уровень][трассировка][исполняемая строка] сообщение.
Уровень берётся из env-переменной LOG_LEVEL (по умолчанию INFO).
"""

import contextvars
import logging
import os
import sys
from typing import Any, Dict

from app.config import settings

# Контекст для трассировочных идентификаторов (например, REQUEST-UUID, TRANSACTION-ID)
trace_ctx: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar("trace_ctx", default={})


_RESET = "\033[0m"
_LEVEL_COLORS = {
    "DEBUG": "\033[90m",      # Grey
    "INFO": "\033[32m",       # Green
    "WARNING": "\033[33m",    # Yellow
    "ERROR": "\033[31m",      # Red
    "CRITICAL": "\033[1;31m", # Bold Red
}
_CYAN = "\033[36m"
_BLUE = "\033[94m"


class CustomFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        # Форматируем время с добавлением миллисекунд (через запятую)
        t = self.formatTime(record, self.datefmt)
        asctime_ms = f"{t},{int(record.msecs):03d}"
        asctime_ms_str = f"{_BLUE}{asctime_ms}{_RESET}"

        levelname = record.levelname
        color = _LEVEL_COLORS.get(levelname, "")
        levelname_str = f"{color}{levelname}{_RESET}" if color else levelname

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
            ctx_str = f"{_CYAN}{ctx_content}{_RESET}"

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


def setup_logging() -> None:
    """Инициализирует логирование всего приложения. Вызывать один раз при старте."""
    # Выводим ASCII-баннер в stdout перед настройкой логгеров
    banner_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "rating_v2.txt")
    if os.path.exists(banner_path):
        try:
            with open(banner_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()
                if lines:
                    max_w = max(len(line) for line in lines)
                    max_h = len(lines)
                    diagonal_coeff = 4.0
                    max_val = (max_w - 1) + (max_h - 1) * diagonal_coeff
                    
                    colors = [
                        (79, 70, 229),   # Indigo
                        (147, 51, 234),  # Violet
                        (236, 72, 153),  # Pink
                    ]
                    
                    def get_gradient_color(t: float) -> tuple[int, int, int]:
                        t = max(0.0, min(1.0, t))
                        if t >= 1.0:
                            return colors[-1]
                        segment_size = 1.0 / (len(colors) - 1)
                        segment_idx = int(t // segment_size)
                        local_t = (t - (segment_idx * segment_size)) / segment_size
                        c1 = colors[segment_idx]
                        c2 = colors[segment_idx + 1]
                        r = int(c1[0] + (c2[0] - c1[0]) * local_t)
                        g = int(c1[1] + (c2[1] - c1[1]) * local_t)
                        b = int(c1[2] + (c2[2] - c1[2]) * local_t)
                        return r, g, b

                    colored_lines = []
                    for row_idx, line in enumerate(lines):
                        colored_chars = []
                        for col_idx, char in enumerate(line):
                            if char.isspace():
                                colored_chars.append(char)
                            else:
                                val = col_idx + row_idx * diagonal_coeff
                                t = val / max_val if max_val > 0 else 0
                                r, g, b = get_gradient_color(t)
                                colored_chars.append(f"\033[38;2;{r};{g};{b}m{char}\033[0m")
                        colored_lines.append("".join(colored_chars))
                    
                    sys.stdout.write("\n".join(colored_lines) + "\n")
                    sys.stdout.flush()
        except Exception:
            pass

    level_str = settings.log_level.upper()
    if level_str == "DEV":
        level = logging.INFO
    else:
        level = logging.DEBUG

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

