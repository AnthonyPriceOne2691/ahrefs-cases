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
