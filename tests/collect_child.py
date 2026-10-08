"""Сбор в отдельном процессе — для краш-теста M98 (`tests/test_collect_stop.py`).

`python tests/collect_child.py <домен,домен,…>`: собирает шаг 1 фикстурным провайдером, а на третьем
запросе печатает строку «в сети: <домен>» и «висит в сети», пока тест не убьёт процесс SIGKILL.
Смерть процесса имитировать исключением нельзя: исключение проходит через `except` и `finally` сбора, а
SIGKILL — нет, и ради этого случая написаны чекпойнты и реапер (Z52).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.provider import HistoryRequest, HistoryResult
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.storage.session import get_sessionmaker

HANG_ON = 3
IN_FLIGHT = "в сети: "
NOW = date(2026, 9, 15)


class HangingFixture(AhrefsFixture):
    """Фикстура, у которой запрос номер `HANG_ON` уходит «в сеть» и не возвращается."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        self.calls += 1
        if self.calls == HANG_ON:
            print(f"{IN_FLIGHT}{request.target}", flush=True)
            await asyncio.Event().wait()
        return await super().fetch_history(spec, request)


async def main(domains: list[str]) -> None:
    async with get_sessionmaker()() as session:
        await collect_all(session, HangingFixture(), now=NOW, only=domains)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].split(",")))
