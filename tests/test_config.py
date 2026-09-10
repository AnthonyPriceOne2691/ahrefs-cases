"""Конфиг: дефолты, fail-fast и разбор backoff.

Примеры приёмки: A4 (дефолты без .env), A5 (live без ключа).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ahrefs_cases.config.ahrefs import AhrefsSettings


def test_defaults_without_env_file() -> None:
    """A4: импорт конфига без .env даёт fixture-провайдер и не бросает исключений."""
    settings = AhrefsSettings(_env_file=None)

    assert settings.provider == "fixture"
    assert settings.api_key == ""
    assert settings.history_grouping == "monthly"
    assert settings.retry_backoff_sec == (1.0, 5.0, 30.0)


def test_live_without_key_fails_fast() -> None:
    """A5: live без ключа падает на конструировании конфига.

    Проверяется здесь, а не запуском процесса с переменной окружения: права
    агента запрещают ставить `AHREFS_PROVIDER=live` из шелла (это защита квоты
    заказчика), и правильное место для проверки поведения — тест.
    """
    with pytest.raises(ValidationError) as excinfo:
        AhrefsSettings(_env_file=None, provider="live", api_key="")

    assert "AHREFS_API_KEY" in str(excinfo.value)


def test_live_with_key_is_accepted() -> None:
    """Обратная сторона A5: с ключом live-конфиг собирается.

    Без этого теста валидатор мог бы запрещать live всегда, и запрет выглядел бы
    как работающая проверка.
    """
    settings = AhrefsSettings(_env_file=None, provider="live", api_key="not-a-real-key")

    assert settings.provider == "live"


@given(
    st.lists(
        st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=10,
    )
)
def test_backoff_round_trip(values: list[float]) -> None:
    """Реляционный оракул: разбор — обратная операция к записи.

    `parse(format(xs)) == xs` для любого списка задержек. Свойство, а не пример:
    в нём нет ожидаемого значения, поэтому в нём нельзя спрятать неверное
    ожидание — а раннер перебирает входы, о которых автор не думал.
    """
    serialized = ",".join(repr(v) for v in values)

    settings = AhrefsSettings(_env_file=None, retry_backoff_sec=serialized)

    assert settings.retry_backoff_sec == tuple(values)


@given(st.text(alphabet=" ,", max_size=8))
def test_backoff_blank_input_keeps_tuple_type(blank: str) -> None:
    """Пустой и пробельный вход даёт кортеж, а не None и не исключение.

    Граничный случай из практики: `AHREFS_RETRY_BACKOFF_SEC=` в .env — законная
    запись, и она обязана означать «пусто», а не ронять старт сервиса.
    """
    settings = AhrefsSettings(_env_file=None, retry_backoff_sec=blank)

    assert isinstance(settings.retry_backoff_sec, tuple)


def test_collect_scheme_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """L4: переменная окружения читается по алиасу, и это надо проверять env'ом.

    Опечатка в `validation_alias` здесь молчит громче обычного: умолчание
    `history` — это и есть выключенное состояние флага. Оператор поставил бы
    `AHREFS_COLLECT_SCHEME=auto`, увидел бы прежнюю смету и решил, что точки не
    дешевле истории. Поэтому тест ставит **переменную**, а не поле: конструктор
    по имени поля прошёл бы и при неверном алиасе.
    """
    monkeypatch.setenv("AHREFS_COLLECT_SCHEME", "auto")

    assert AhrefsSettings(_env_file=None).collect_scheme == "auto"

    monkeypatch.setenv("AHREFS_COLLECT_SCHEME", "points")
    with pytest.raises(ValidationError) as excinfo:
        AhrefsSettings(_env_file=None)
    assert "AHREFS_COLLECT_SCHEME" in str(excinfo.value), (
        "ошибка называет переменную окружения, а не поле: правит её человек, а не код"
    )


def test_history_lead_is_zero_by_default() -> None:
    """E8: запас до старта работ по умолчанию не покупается.

    Было три месяца безусловно — 33 units на домен при построчном биллинге.
    Число живёт в конфиге, поэтому и проверяется здесь: правка «обратно на три»
    прошла бы незаметно, а стоила бы 3300 units на каждом прогоне по сотне.
    """
    assert AhrefsSettings(_env_file=None).history_lead_months == 0
