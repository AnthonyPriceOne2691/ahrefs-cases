"""Оракул области действия: тест правит своё, а не таблицу.

Зачем он вообще. Уборка `delete(Model)` без условия выглядит как аккуратность и
даёт зелёный прогон — тест ведь убрал за собой. Беда видна только со стороны:
по данным, о которых тест не знает. На общей дев-базе (а она общая нарочно: на
ней смотрят экраны и готовят показ) такая уборка уносит чужую работу молча.

Так и нашлось — показом карточки: проект, час назад бывший «хорошим», стал
«не классифицированным», потому что между делом кто-то прогнал `pytest`
(урок L79). Ни один гейт этого не ловил: они смотрят на форму кода, а не на
область действия удаления.

Правило: у каждого `delete(...)` и `update(...)` в `tests/` должно быть условие.
`update` попал сюда не из симметрии: тест замка на второй прогон помечал
«идущим» **каждый** прогон в базе, и чужие оставались такими навсегда —
следующий запуск упирался в чужой замок. Нашлось этой же поставкой, когда
уборка перестала прятать следы, стирая всё подряд.

Набор, который и правда принадлежит тесту целиком, помечается строкой
`# cleanup-all-ok: <причина>` — как и прочие осознанные исключения в проекте.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ALLOW_MARK = "cleanup-all-ok:"
WIDE_CALLS = frozenset({"delete", "update"})


def _guarded_calls(tree: ast.AST) -> set[int]:
    """Идентификаторы вызовов `delete(...)`, к которым прицеплено условие.

    `delete(Model).where(...)` — это `Call(func=Attribute(attr='where',
    value=Call(...)))`: внутренний вызов и есть защищённый.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"where", "filter"}
            and isinstance(node.func.value, ast.Call)
        ):
            guarded.add(id(node.func.value))
    return guarded


def _unscoped_writes(path: Path) -> list[int]:
    """Строки, где `delete(...)` или `update(...)` вызван без условия и пометки."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    guarded = _guarded_calls(tree)

    found: list[int] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in WIDE_CALLS or id(node) in guarded:
            continue
        # Пометка ищется на строке вызова: она объявляет осознанное исключение
        # там, где его видно вместе с кодом.
        if ALLOW_MARK in lines[node.lineno - 1]:
            continue
        found.append(node.lineno)
    return found


def test_tests_delete_only_their_own_rows() -> None:
    """E1: правка без условия в тестах запрещена и названа поимённо."""
    offenders: list[str] = []
    for path in [*sorted(TESTS_DIR.rglob("test_*.py")), TESTS_DIR / "owned_rows.py"]:
        offenders.extend(f"{path.name}:{line}" for line in _unscoped_writes(path))

    assert not offenders, (
        "правка без условия заденет чужие строки в общей дев-базе: "
        + ", ".join(offenders)
        + ". Удаляйте по владению (`tests/owned_rows.delete_owned`) либо "
        f"пометьте строку `# {ALLOW_MARK} <причина>`"
    )


def test_oracle_sees_a_bare_delete(tmp_path: Path) -> None:
    """E1 наоборот: оракул обязан замечать нарушение — и удаление, и правку.

    Проверка самого оракула, потому что «ничего не нашёл» — тот же результат,
    что «не умеет искать».
    """
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "session.execute(delete(Run))\nsession.execute(update(Run).values(status=1))\n",
        encoding="utf-8",
    )

    assert _unscoped_writes(sample) == [1, 2]


def test_condition_and_mark_are_accepted(tmp_path: Path) -> None:
    """E2 и E3: условие и явная пометка — законные способы пройти."""
    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "session.execute(delete(Run).where(Run.id == 1))\n"
        "session.execute(delete(Run))  # cleanup-all-ok: таблица только для этого теста\n",
        encoding="utf-8",
    )

    assert _unscoped_writes(sample) == []
