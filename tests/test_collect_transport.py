"""Транспорт Ahrefs и разбор ответа живого провайдера.

Живой ключ здесь не участвует и участвовать не может: тесты, жгущие units,
нестабильны и стоят денег заказчика (§10 документа реализации). Проверяется то,
что от ключа не зависит, — повторы, коды ответа, разбор тела и заголовков цены.

Примеры приёмки: B12 (live без ключа не стартует).
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from ahrefs_cases.collect.ahrefs_transport import (
    AhrefsHTTPError,
    AhrefsTransport,
    AhrefsUnavailableError,
)
from ahrefs_cases.collect.endpoints import (
    METRICS_HISTORY,
    EndpointSpec,
)
from ahrefs_cases.collect.live import AhrefsLive
from ahrefs_cases.collect.provider import HistoryRequest
from ahrefs_cases.storage._enums import Metric, MetricSource, TargetMode

REQUEST = HistoryRequest(
    target="example.com",
    mode=TargetMode.SUBDOMAINS,
    country="US",
    date_from=date(2025, 1, 1),
)

PAYLOAD = {
    "metrics": [
        {"date": "2025-01-01", "org_traffic": 1000, "org_cost": 500},
        {"date": "2025-02-01T00:00:00Z", "org_traffic": 1200, "org_cost": None},
    ]
}


def _client(handler: object, **kwargs: object) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport, base_url="https://api.ahrefs.test", **kwargs)  # type: ignore[arg-type]


async def test_units_headers_are_read() -> None:
    """B18: фактическая цена берётся из заголовка, а не из нашей оценки.

    Заголовок — единственный источник правды о списании; наша модель стоимости
    останется гипотезой до Ф7, и подменять ею факт значило бы вести журнал units
    по собственным ожиданиям.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=PAYLOAD,
            headers={"x-api-units-cost-total-actual": "63", "x-api-units-cost-total": "50"},
        )

    async with _client(handler) as client:
        response = await AhrefsTransport(client).get(METRICS_HISTORY.path, {})

    assert (response.units_actual, response.units_estimated) == (63, 50)


async def test_missing_units_header_is_zero_not_a_guess() -> None:
    """B18: нет заголовка — ноль и запись в лог, а не подстановка оценки.

    Журнал units обязан отличать «стоило ноль» от «мы не узнали цену»; вторая
    ситуация видна расхождением с оценкой, если её не затереть этой же оценкой.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD)

    async with _client(handler) as client:
        response = await AhrefsTransport(client).get(METRICS_HISTORY.path, {})

    assert response.units_actual == 0


async def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """B18: 429 повторяется — лимит запросов есть временное состояние, а не отказ."""
    monkeypatch.setattr("ahrefs_cases.collect.ahrefs_transport.asyncio.sleep", _no_sleep)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=PAYLOAD, headers={"x-api-units-cost-total-actual": "50"})

    async with _client(handler) as client:
        response = await AhrefsTransport(client).get(METRICS_HISTORY.path, {})

    assert calls["n"] == 2
    assert response.units_actual == 50


async def test_bad_key_is_not_retried() -> None:
    """B18: 401 не повторяется — три попытки с неверным ключом дают три записи и ноль пользы."""
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, text="unauthorized")

    async with _client(handler) as client:
        with pytest.raises(AhrefsHTTPError):
            await AhrefsTransport(client).get(METRICS_HISTORY.path, {})

    assert calls["n"] == 1


async def test_gives_up_with_named_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """B18: после всех попыток — внятная ошибка, а не пустой результат.

    Пустой результат означал бы «у домена нет истории», и прогон записал бы
    молодой домен и упавший Ahrefs одинаково.
    """
    monkeypatch.setattr("ahrefs_cases.collect.ahrefs_transport.asyncio.sleep", _no_sleep)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with _client(handler) as client:
        with pytest.raises(AhrefsUnavailableError, match="503"):
            await AhrefsTransport(client).get(METRICS_HISTORY.path, {})


async def test_live_parses_points_and_skips_none() -> None:
    """B8: `None` в значении пропускается, а не становится нулём.

    Ноль вместо пропуска превратил бы месяц без данных в месяц с нулевым
    трафиком, и классификация Ф3 увидела бы провал там, где его не было.
    """

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=PAYLOAD, headers={"x-api-units-cost-total-actual": "50"})

    async with _client(handler) as client:
        result = await AhrefsLive(AhrefsTransport(client)).fetch_history(METRICS_HISTORY, REQUEST)

    assert [point.at.isoformat() for point in result.points] == ["2025-01-01", "2025-02-01"]
    assert result.points[1].values == {Metric.ORG_TRAFFIC: 1200.0}
    assert result.source == MetricSource.LIVE


async def test_live_sends_minimal_select() -> None:
    """B18: `select` уходит минимальным — каждое лишнее поле metrics-history это +10 units."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"metrics": []}, headers={})

    async with _client(handler) as client:
        await AhrefsLive(AhrefsTransport(client)).fetch_history(METRICS_HISTORY, REQUEST)

    assert seen["select"] == "date,org_traffic,org_cost"
    assert "paid_traffic" not in seen["select"]
    assert seen["history_grouping"] == "monthly"
    assert seen["mode"] == "subdomains"


def test_cost_model_is_one_place() -> None:
    """B10: модель стоимости считает по спеке endpoint'а, а не по имени в коде."""
    # Замерено живым ключом: строка стоит 10 за поле плюс 1, минимум запроса 50.
    assert METRICS_HISTORY.row_units() == 21, "два поля: 10×2+1"
    assert METRICS_HISTORY.estimate_units(rows=1) == 50, "минимум запроса бьёт цену строки"
    assert METRICS_HISTORY.estimate_units(rows=3) == 63
    assert METRICS_HISTORY.estimate_units(rows=21) == 441

    one_field = EndpointSpec(
        name="one-field",
        path="/x",
        select=("date", "org_traffic"),
        list_key="rows",
        metrics={},
        stage=1,
    )
    assert one_field.row_units() == 11, "одно поле: 10×1+1"
    assert one_field.estimate_units(rows=9) == 99


async def _no_sleep(_seconds: float) -> None:
    """Backoff в тестах не ждёт: проверяем число попыток, а не терпение."""
