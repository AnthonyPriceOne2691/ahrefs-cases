"""Коды возврата CLI. Пример приёмки: C15.

Единственный тест, запускающий скрипт как процесс: коды возврата и вывод в
stderr — это и есть его контракт, и проверить их вызовом функции нельзя.
Сеть и база здесь не нужны: все случаи отсекаются до подключения к чему-либо.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_collect.py"
_EXIT_BAD_SOURCE = 2


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.mark.parametrize(
    ("source", "expected_text"),
    [
        ("нет-такого.csv", "файл не найден"),
        ("список.pdf", "не понимаю источник"),
        ("https://example.com/list", "не понимаю источник"),
    ],
)
def test_unreadable_source_exits_with_two(source: str, expected_text: str) -> None:
    """C15: причина строкой в stderr и код 2 — не трассировка `io.open`.

    Опечатка в пути — самая частая ошибка запуска. Ответ трассировкой заставил
    бы человека читать стек ради строки «файла нет».
    """
    result = _run("intake", source)

    assert result.returncode == _EXIT_BAD_SOURCE
    assert expected_text in result.stderr
    assert "Traceback" not in result.stderr


def test_help_works_without_database() -> None:
    """`--help` не должен требовать ни базы, ни ключа: им пользуются до настройки."""
    result = _run("--help")

    assert result.returncode == 0
    assert "stage2" in result.stdout
