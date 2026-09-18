"""Настройка логирования: поля из `extra` обязаны дожить до вывода.

**Гейт `unstructured-log` без этого модуля — плаченный и не полученный.**
Правило «значение идёт в `extra={...}`, а не вплавляется в текст» стоит
дисциплины на каждом вызове логгера, и в этом проекте оно соблюдается.
Но стандартный форматтер печатает только `%(message)s`: всё, что передано
в `extra`, он молча выбрасывает. Цену платит автор кода, получить её не
может никто — полей в выводе просто нет. Класс тот же, что у пропущенной
проверки: выглядит работающим, потому что ничего не ломает.

**Без сквозного идентификатора прогона логи не отвечают на главный вопрос.**
«Что происходило в прогоне 47» — это не поиск по времени: прогоны идут
параллельно, строки перемешаны. Идентификатор кладётся в контекст один раз
и попадает в каждую запись сам, включая те, что пишут библиотеки внутри
наших вызовов.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from ahrefs_cases import config

#: Пустая строка — код вызван вне прогона (разовая команда, тест). Это
#: законно: поле тогда не печатается в текстовом формате.
_run_id: ContextVar[str] = ContextVar("run_id", default="")

#: Поля, которые `logging` кладёт в запись сам. Всё прочее пришло из `extra`.
_STANDARD_FIELDS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def current_run_id() -> str:
    """Идентификатор прогона, к которому относится текущий код."""
    return _run_id.get()


@contextmanager
def run_context(run_id: str | int) -> Iterator[None]:
    """Пометить все записи внутри блока идентификатором прогона."""
    token = _run_id.set(str(run_id))
    try:
        yield
    finally:
        _run_id.reset(token)


class RunIdFilter(logging.Filter):
    """Проставляет `run_id` каждой записи, включая чужие.

    Фильтр висит на хендлере, а не на логгере: записи библиотек идут через
    свои логгеры, и наше поле иначе на них не попадёт.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get()
        return True


def _extra_fields(record: logging.LogRecord) -> dict[str, object]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _STANDARD_FIELDS and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """Одна запись — одна строка JSON. Поля из `extra` остаются полями."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # `default=str`: в extra попадают доменные объекты, и падение
        # логгера на несериализуемом поле — худший из исходов.
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Человеческая строка, но поля из `extra` не теряются — они в хвосте."""

    def __init__(self) -> None:
        super().__init__("%(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = {k: v for k, v in _extra_fields(record).items() if v not in ("", None)}
        if not fields:
            return line
        return line + " | " + " ".join(f"{k}={v}" for k, v in sorted(fields.items()))


def setup_logging(level: str | None = None, fmt: str | None = None) -> None:
    """Собрать корневой логгер. Вызывается один раз в точке входа.

    Повторный вызов заменяет хендлеры, а не добавляет вторые: иначе каждая
    запись печатается дважды — первое, что ломается при запуске команды
    из тестов.
    """
    chosen_level = (level or config.logs.level).upper()
    chosen_format = (fmt or config.logs.format).lower()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if chosen_format == "json" else TextFormatter())
    handler.addFilter(RunIdFilter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(chosen_level)
