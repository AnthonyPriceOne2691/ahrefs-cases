"""Причина падения в журнале: первая ошибка, а не последняя.

Живой прогон 13.09.2026: задача воркера упала `AttributeError` (в памяти
процесса был старый модуль конфига), запись причины упала следом
`MissingGreenlet` — и в журнале осталась вторая. Оператор видит в таблице
прогонов ошибку про событийный цикл и чинит не то; настоящая причина остаётся
в логах контейнера, куда у него нет доступа.

Тестами это не ловилось и не могло: тест падает одним исключением.
"""

from __future__ import annotations

import pytest

from ahrefs_cases.collect.run_journal import failure_reason


def _chained() -> Exception:
    """Вторая ошибка, случившаяся при обработке первой, — как в живом падении."""
    try:
        raise AttributeError("'AhrefsSettings' object has no attribute 'units_counter_lag_hours'")
    except AttributeError:
        try:
            raise RuntimeError("greenlet_spawn has not been called")
        except RuntimeError as second:
            return second


def test_recorded_reason_names_the_root_cause() -> None:
    """E4: в строке видны обе ошибки, и первопричина названа словом.

    Последняя — потому что она ближе к месту падения; первая — потому что она
    объясняет. Одной мало: ровно на этом живой прогон и отправил чинить
    событийный цикл вместо перезапуска воркера.
    """
    reason = failure_reason(_chained())

    assert "RuntimeError" in reason
    assert "первопричина" in reason
    assert "units_counter_lag_hours" in reason


def test_single_error_reads_as_before() -> None:
    """E5: одиночная ошибка не обрастает хвостами.

    Большинство падений одиночные, и приписка «первопричина — то же самое»
    сделала бы журнал шумным ровно там, где он и так понятен.
    """
    reason = failure_reason(ValueError("в базе нет проектов: example.com"))

    assert reason == "ValueError: в базе нет проектов: example.com"


def test_reason_stays_one_readable_line() -> None:
    """Строку читают глазами в таблице прогонов — она не может быть трактатом."""
    long_text = "ы" * 5000

    reason = failure_reason(ValueError(long_text))

    assert len(reason) <= 400


def test_cycles_in_the_chain_do_not_hang_it() -> None:
    """Цепочка может ссылаться сама на себя — обход обязан закончиться.

    Так бывает при повторном `raise` уже пойманного исключения; бесконечный
    цикл здесь остановил бы запись причины совсем, то есть съел бы её целиком.
    """
    first = ValueError("первая")
    second = RuntimeError("вторая")
    second.__context__ = first
    first.__context__ = second

    reason = failure_reason(second)

    assert "RuntimeError: вторая" in reason
    assert "первопричина" in reason


@pytest.mark.parametrize("kind", ["__cause__", "__context__"])
def test_both_kinds_of_chaining_are_followed(kind: str) -> None:
    """`raise ... from` и «упало при обработке» — обе цепочки одинаково важны."""
    root = KeyError("корень")
    top = RuntimeError("верх")
    setattr(top, kind, root)

    assert "корень" in failure_reason(top)
