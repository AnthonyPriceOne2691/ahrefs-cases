"""Single-flight: одновременные запросы по одному домену склеиваются в один.

Пример приёмки: C4. Проверяется числом обращений к провайдеру, а не логами:
«сделали один запрос» — утверждение о деньгах, и оно должно быть посчитано.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from ahrefs_cases.collect.endpoints import METRICS_HISTORY, EndpointSpec
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult
from ahrefs_cases.collect.single_flight import SingleFlightProvider
from ahrefs_cases.storage._enums import MetricSource, TargetMode


def _request(target: str, *, date_from: date = date(2025, 1, 1)) -> HistoryRequest:
    return HistoryRequest(
        target=target,
        mode=TargetMode.SUBDOMAINS,
        country="US",
        date_from=date_from,
        date_to=date(2026, 6, 1),
    )


class SlowCountingFixture(AhrefsFixture):
    """Медленный провайдер: без задержки запросы не пересекаются во времени."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls.append(f"{request.target}@{request.date_from}")
        await asyncio.sleep(0.01)
        return await super().fetch_history(spec, request)


async def test_same_domain_asked_once() -> None:
    """C4: три одновременных запроса по одному домену — один вызов провайдера.

    Один домен закажут разные отделы; без склейки агентство платит за одну и ту
    же историю столько раз, сколько человек нажали кнопку.
    """
    inner = SlowCountingFixture()
    provider = SingleFlightProvider(inner)

    results = await asyncio.gather(
        *(provider.fetch_history(METRICS_HISTORY, _request("d1.example.com")) for _ in range(3))
    )

    assert len(inner.calls) == 1
    assert all(result.points == results[0].points for result in results)


async def test_different_domains_are_not_blocked() -> None:
    """Обратная сторона C4: склейка не должна превращаться в очередь из одного.

    Без этой проверки реализация «один запрос за раз» прошла бы предыдущий тест
    и убила бы параллельность прогона на сотне доменов.
    """
    inner = SlowCountingFixture()
    provider = SingleFlightProvider(inner)

    await asyncio.gather(
        provider.fetch_history(METRICS_HISTORY, _request("d1.example.com")),
        provider.fetch_history(METRICS_HISTORY, _request("d2.example.com")),
    )

    assert sorted(inner.calls) == ["d1.example.com@2025-01-01", "d2.example.com@2025-01-01"]


async def test_different_windows_are_not_merged() -> None:
    """Разные `date_from` — разные данные, склеивать нельзя.

    Один прогон идёт инкрементально, другой с `--refresh`: выдать второму ответ
    первого значило бы молча отдать не те данные, и заметить это было бы
    нечем — точки легли бы в базу как настоящие.
    """
    inner = SlowCountingFixture()
    provider = SingleFlightProvider(inner)

    await asyncio.gather(
        provider.fetch_history(METRICS_HISTORY, _request("d1.example.com")),
        provider.fetch_history(
            METRICS_HISTORY, _request("d1.example.com", date_from=date(2024, 1, 1))
        ),
    )

    assert len(inner.calls) == 2


async def test_failed_request_does_not_lock_the_domain() -> None:
    """Упавший запрос не должен сделать домен неопрашиваемым.

    Ключ снимается в `finally`: иначе одна ошибка блокировала бы домен до
    перезапуска процесса, и это выглядело бы как «Ahrefs не отвечает по
    одному конкретному сайту».
    """

    class Failing(AhrefsFixture):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
            self.calls += 1
            if self.calls == 1:
                message = "первый раз падаем"
                raise RuntimeError(message)
            return await super().fetch_history(spec, request)

    inner = Failing()
    provider = SingleFlightProvider(inner)

    with pytest.raises(RuntimeError):
        await provider.fetch_history(METRICS_HISTORY, _request("d1.example.com"))

    result = await provider.fetch_history(METRICS_HISTORY, _request("d1.example.com"))

    assert inner.calls == 2
    assert result.source is MetricSource.FIXTURE


async def test_source_is_passed_through() -> None:
    """Обёртка не подменяет источник данных: точки помечаются как у обёрнутого."""
    provider = SingleFlightProvider(AhrefsFixture())

    assert provider.source is MetricSource.FIXTURE
