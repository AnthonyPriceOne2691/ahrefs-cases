"""Идентификатор прогона обязан стоять в записях, а не только существовать.

Механизм пометки сам по себе ничего не доказывает: пока его никто не
вызывает, каждая запись уходит с пустым `run_id`, и вопрос «что было в
прогоне 47» по логам остаётся без ответа. Задачи идут параллельно, их
строки в логе перемешаны — метка и есть единственный способ их разделить.

Проверяется поэтому не наличие обёртки в исходнике, а то, что метка видна
изнутри работы и снимается после неё.
"""

from __future__ import annotations

from typing import Any

import pytest

from ahrefs_cases.logs import current_run_id
from ahrefs_cases.workers import jobs


@pytest.fixture
def _quiet_finish(monkeypatch: pytest.MonkeyPatch) -> None:
    """Предмет теста — метка, а не закрытие прогона: база здесь лишняя."""

    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(jobs, "_finish", _noop)
    monkeypatch.setattr(jobs, "dispose_engine", _noop)


@pytest.mark.usefixtures("_quiet_finish")
async def test_work_sees_the_run_id() -> None:
    seen: list[str] = []

    async def work() -> str:
        seen.append(current_run_id())
        return "готово"

    await jobs._run_guarded(47, work())
    assert seen == ["47"]


@pytest.mark.usefixtures("_quiet_finish")
async def test_the_mark_is_dropped_after_the_job() -> None:
    """Иначе следующая задача в том же процессе унаследует чужой прогон."""

    async def work() -> str:
        return "готово"

    await jobs._run_guarded(47, work())
    assert current_run_id() == ""


@pytest.mark.usefixtures("_quiet_finish")
async def test_the_mark_survives_a_failing_job() -> None:
    """Запись о падении — самая нужная, и она обязана быть адресуемой."""
    seen: list[str] = []

    async def work() -> str:
        seen.append(current_run_id())
        raise RuntimeError("упало")

    with pytest.raises(RuntimeError, match="упало"):
        await jobs._run_guarded(47, work())
    assert seen == ["47"]
    assert current_run_id() == ""
