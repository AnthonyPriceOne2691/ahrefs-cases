"""Форма ответа Ahrefs: неверная догадка падает громко, а не молчит.

Проверяем не сами формы — их подтвердит только живой ключ (Z2, Z3 в
`docs/FINDINGS.md`), — а то, **как** они ломаются. Сегодня это важнее: пока
догадка молчит, ошибка в имени ключа выглядит как «у ста доменов нет истории»,
и сервис отчитывается успехом, потратив units.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from ahrefs_cases.collect.ahrefs_transport import AhrefsTransport
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.collect.live import AhrefsLive
from ahrefs_cases.collect.provider import HistoryRequest
from ahrefs_cases.collect.quota import FixtureQuota, LiveQuota, QuotaVerdict, preflight
from ahrefs_cases.collect.response_guard import (
    AhrefsResponseError,
    require_int,
    require_rows,
    warn_if_shallower_than_asked,
)
from ahrefs_cases.storage._enums import TargetMode

REQUEST = HistoryRequest(
    target="example.com",
    mode=TargetMode.SUBDOMAINS,
    country="US",
    date_from=date(2025, 1, 1),
    date_to=date(2026, 6, 1),
)


def _client(handler: object) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        base_url="https://api.ahrefs.test",
    )


async def test_wrong_list_key_is_an_error_not_empty_history() -> None:
    """Z3: другой ключ списка — ошибка формы, а не «у домена нет истории».

    Разница решающая: пустая история помечает домен `no_data` и, после
    подтверждения, замолкает о нём на месяц. Ошибка формы обязана дойти до
    человека в первом же прогоне.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [{"date": "2025-01-01", "org_traffic": 10}]})

    async with _client(handler) as client:
        with pytest.raises(AhrefsResponseError, match="metrics"):
            await AhrefsLive(AhrefsTransport(client)).fetch_history(METRICS_HISTORY, REQUEST)


async def test_empty_list_is_still_empty_history() -> None:
    """Обратная сторона: пустой список по правильному ключу — штатный случай.

    Если бы строгая проверка ломалась и здесь, молодые домены превратились бы
    в ошибки прогона, а прогон — в `partial` без причины.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"metrics": []})

    async with _client(handler) as client:
        result = await AhrefsLive(AhrefsTransport(client)).fetch_history(METRICS_HISTORY, REQUEST)

    assert result.is_empty


async def test_wrong_field_names_are_caught() -> None:
    """Z3: ключ списка верный, а имена полей нет — серия не должна быть пустой.

    Без проверки точки пришли бы без значений, и классификация назвала бы
    живой проект «нет данных» — то есть ошибка формы стала бы выводом о
    клиенте.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"metrics": [{"date": "2025-01-01", "traffic": 10, "cost": 5}]}
        )

    async with _client(handler) as client:
        with pytest.raises(AhrefsResponseError, match="не разобрано"):
            await AhrefsLive(AhrefsTransport(client)).fetch_history(METRICS_HISTORY, REQUEST)


async def test_quota_without_keys_is_unknown_not_zero() -> None:
    """Z2: нет полей остатка — «не знаем», а не «остаток ноль».

    Ноль при fail-closed означает вечный запрет прогонов, и выглядит это как
    исчерпанная квота клиента, хотя причина — наши угаданные имена полей.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"limits": {"units": 10_000}})

    async with _client(handler) as client:
        state = await preflight(LiveQuota(AhrefsTransport(client)), needed=100)

    assert state.verdict is QuotaVerdict.UNKNOWN
    assert "units_limit" in state.reason


async def test_quota_with_expected_keys_works() -> None:
    """Обратная сторона Z2: ожидаемая форма разбирается и даёт остаток."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"units_limit": 10_000, "units_usage": 2_500})

    async with _client(handler) as client:
        left = await LiveQuota(AhrefsTransport(client)).units_left()

    assert left == 7_500


def test_require_int_distinguishes_missing_from_zero() -> None:
    """Ноль — законное значение; отсутствие ключа — нет."""
    assert require_int({"units_limit": 0}, "units_limit", "test") == 0

    with pytest.raises(AhrefsResponseError):
        require_int({}, "units_limit", "test")


def test_require_rows_rejects_non_list() -> None:
    """По ключу пришёл объект вместо списка — тоже расхождение формы."""
    with pytest.raises(AhrefsResponseError, match="ожидался список"):
        require_rows({"metrics": {"date": "2025-01-01"}}, "metrics", "metrics-history")


def test_shallow_history_is_measured() -> None:
    """H3: сколько месяцев истории недодали — считаем, а не догадываемся.

    Число уходит в лог и доступно вызывающему: «просили 24 месяца, дали 9» —
    это про тариф, а не про домен, и путать их нельзя.
    """
    got = [date(2025, 10, 1), date(2025, 11, 1)]

    missing = warn_if_shallower_than_asked(got, date(2025, 1, 1), "metrics-history", "example.com")

    assert missing == 9


def test_fixture_quota_is_unaffected() -> None:
    """Дев-режим не должен зависеть от формы живого ответа."""
    assert FixtureQuota(left=42).left == 42


def test_estimate_drift_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    """H1: расхождение сметы с фактом обязано быть слышно в первом же прогоне.

    Модель стоимости — гипотеза: документация Ahrefs называет и минимум 50
    units, и цену `refdomains-history` в 5, не объясняя их сочетания. Если
    модель неверна, это выяснится либо здесь, либо из счёта в конце месяца.
    """
    import logging

    from ahrefs_cases.collect.budget import _warn_if_estimate_missed
    from ahrefs_cases.collect.provider import HistoryResult
    from ahrefs_cases.storage._enums import MetricSource

    result = HistoryResult(
        endpoint="metrics-history",
        target="example.com",
        points=(),
        units_estimated=50,
        units_actual=180,
        source=MetricSource.LIVE,
    )

    with caplog.at_level(logging.WARNING):
        _warn_if_estimate_missed(result)

    assert "ahrefs_estimate_missed" in caplog.text


def test_estimate_within_tolerance_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    """Обратная сторона H1: небольшое расхождение не шумит.

    Предупреждение, срабатывающее на каждом ответе, перестают читать — и
    настоящее расхождение утонет вместе с остальными.
    """
    import logging

    from ahrefs_cases.collect.budget import _warn_if_estimate_missed
    from ahrefs_cases.collect.provider import HistoryResult
    from ahrefs_cases.storage._enums import MetricSource

    result = HistoryResult(
        endpoint="metrics-history",
        target="example.com",
        points=(),
        units_estimated=50,
        units_actual=55,
        source=MetricSource.LIVE,
    )

    with caplog.at_level(logging.WARNING):
        _warn_if_estimate_missed(result)

    assert caplog.text == ""
