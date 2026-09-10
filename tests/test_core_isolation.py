"""Архитектурный инвариант: ядро не знает про веб.

Это правило из `delivery/CONSTITUTION.md`, и оно должно отклонять, а не жить
обещанием: как только ядро потянет FastAPI или RQ, его нельзя будет
тестировать без сервера, а обвязку — заменить, не задевая расчёты.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_CORE = ("intake", "collect", "classify", "cases", "export", "storage", "config")
_FORBIDDEN = {"fastapi", "starlette", "rq", "uvicorn"}
_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "ahrefs_cases"


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


@pytest.mark.parametrize("package", _CORE)
def test_core_package_does_not_import_web(package: str) -> None:
    offenders: list[str] = []
    for path in sorted((_SRC / package).rglob("*.py")):
        leaked = _imports(path) & _FORBIDDEN
        if leaked:
            offenders.append(f"{path.relative_to(_SRC)}: {', '.join(sorted(leaked))}")

    assert not offenders, "ядро потянуло обвязку:\n" + "\n".join(offenders)


def test_test_itself_can_fail() -> None:
    """Проверка проверки: детектор действительно видит запрещённый импорт.

    Без этого теста `_imports` мог бы возвращать пустое множество на любом входе,
    и предыдущий тест был бы зелёным, не просудив ни строки.
    """
    src = "from fastapi import APIRouter\nimport rq\n"
    tmp = pathlib.Path(__file__).with_name("_probe_generated.py")
    tmp.write_text(src, encoding="utf-8")
    try:
        assert _imports(tmp) & _FORBIDDEN == {"fastapi", "rq"}
    finally:
        tmp.unlink()
