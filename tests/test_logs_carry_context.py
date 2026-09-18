"""Логи обязаны доносить `extra` и идентификатор прогона до вывода.

Гейт `unstructured-log` требует класть значения в `extra={...}`, и проект
это соблюдает. Но дисциплина окупается только если хендлер эти поля
печатает: стандартный форматтер их выбрасывает, и тогда правило есть,
а пользы нет. Проверяется поэтому сам вывод, а не наличие настройки.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from ahrefs_cases.logs import current_run_id, run_context, setup_logging


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    saved, level = list(root.handlers), root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in saved:
        root.addHandler(handler)
    root.setLevel(level)


def _emit(capsys: pytest.CaptureFixture[str], fmt: str, **extra: object) -> str:
    setup_logging(level="INFO", fmt=fmt)
    logging.getLogger("test").info("сообщение", extra=extra)
    return capsys.readouterr().err.strip()


def test_extra_fields_reach_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    payload = json.loads(_emit(capsys, "json", domain="example.com", endpoint="metrics"))
    assert payload["domain"] == "example.com"
    assert payload["endpoint"] == "metrics"


def test_extra_fields_reach_text_output(capsys: pytest.CaptureFixture[str]) -> None:
    line = _emit(capsys, "text", domain="example.com", found=0)
    assert "domain=example.com" in line
    # Ноль — это ответ, а не его отсутствие.
    assert "found=0" in line


def test_run_id_marks_foreign_loggers_too(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(level="INFO", fmt="json")
    # Имя своё, а не `httpx`: уровень чужого логгера мог быть поднят где-то
    # ещё в наборе, и тогда запись просто не выйдет — тест упадёт на пустом
    # выводе, хотя проверяемое свойство цело. Ловили в полном прогоне.
    foreign = logging.getLogger("сторонняя.библиотека.проба")
    foreign.setLevel(logging.NOTSET)
    foreign.propagate = True
    with run_context(47):
        foreign.info("чужая запись")
    payload = json.loads(capsys.readouterr().err.strip())
    assert payload["run_id"] == "47"


def test_run_id_is_empty_outside_a_run() -> None:
    assert current_run_id() == ""
    with run_context(1):
        assert current_run_id() == "1"
    assert current_run_id() == ""


def test_setup_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging(level="INFO", fmt="json")
    setup_logging(level="INFO", fmt="json")
    logging.getLogger("test").info("один раз")
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def test_unserializable_value_does_not_break_logging(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert "obj" in json.loads(_emit(capsys, "json", obj=object()))
