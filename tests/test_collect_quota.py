"""Квота, смета и резервы: решение принимается до первого запроса.

Примеры приёмки: C5 (смета учитывает кэш и сходится с фактом), C6 (не хватает
квоты), C7 (остаток неизвестен — fail-closed), C8 (резерв виден чужой смете).
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import AhrefsUnavailableError
from ahrefs_cases.collect.budget import reserved_units
from ahrefs_cases.collect.endpoints import METRICS_HISTORY
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.quota import FixtureQuota, QuotaVerdict, preflight
from ahrefs_cases.collect.run_journal import open_run, start_run, system_user
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import RunStatus
from ahrefs_cases.storage.models.run import Run

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = date(2026, 9, 15)


async def _load(session: AsyncSession, count: int) -> None:
    rows = "\n".join(
        f"d{index}.example.com,2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
        for index in range(count)
    )
    await accept(session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))


class BrokenQuota:
    """Ahrefs не отвечает на бесплатный запрос остатка."""

    async def units_left(self) -> int:
        message = "Ahrefs не ответил за 3 попыт(ок) на /v3/subscription-info"
        raise AhrefsUnavailableError(message)


async def test_estimate_counts_only_what_will_be_asked(db_session: AsyncSession) -> None:
    """C5: смета считает запросы после кэша, а не по числу проектов.

    Шестьдесят собранных доменов из ста не должны стоить ничего — иначе смета
    показывает цену, которой не будет, и «кнопка неактивна» срабатывает на
    прогоне, который влезал в остаток.
    """
    await _load(db_session, 100)
    big = FixtureQuota(left=200_000)
    first = await collect_all(db_session, AhrefsFixture(), now=NOW, quota=big)

    second = await collect_all(db_session, AhrefsFixture(), now=NOW, quota=big)

    # 18 строк окна × 11 units за строку × 100 доменов. Было 21 строка и 21 unit:
    # ушли три месяца запаса до старта работ (читателя у них не было) и второе поле.
    assert first.units_estimated == 100 * METRICS_HISTORY.estimate_units(rows=18)
    assert second.units_estimated == 0


async def test_estimate_matches_the_fact(db_session: AsyncSession) -> None:
    """C5: смета сходится с фактом того же прогона.

    Расхождение больше десятой доли означает, что модель стоимости врёт, и
    узнать об этом надо здесь, а не в Ф7 на деньгах заказчика.
    """
    await _load(db_session, 20)

    report = await collect_all(
        db_session, AhrefsFixture(), now=NOW, quota=FixtureQuota(left=200_000)
    )

    # Смета считает окно запроса (21 месяц), факт — сколько строк реально
    # пришло (18 у сценария). Смета обязана быть НЕ МЕНЬШЕ факта: занизить
    # цену опаснее, чем завысить, — по заниженной смете прогон стартует и
    # упирается в квоту на середине. Верхняя граница держит её от абсурда.
    assert report.units_spent <= report.units_estimated <= report.units_spent * 1.5


async def test_run_does_not_start_without_quota(db_session: AsyncSession) -> None:
    """C6: остатка не хватает — прогон не начат, причина названа числами."""
    await _load(db_session, 10)

    report = await collect_all(db_session, AhrefsFixture(), now=NOW, quota=FixtureQuota(left=100))

    assert report.status == RunStatus.FAILED.value
    assert report.requests_made == 0
    assert "не хватает units" in report.error
    run = (await db_session.execute(select(Run))).scalars().one()
    assert run.started_at is None, "прогон, отклонённый preflight, никогда не начинался"


async def test_unknown_quota_stops_the_run(db_session: AsyncSession) -> None:
    """C7: остаток неизвестен — прогон не начат.

    «Не знаем» трактуется как «не тратим»: цена ошибки в эту сторону —
    отложенный прогон, в другую — потраченные units и половина работы.
    """
    await _load(db_session, 5)

    report = await collect_all(db_session, AhrefsFixture(), now=NOW, quota=BrokenQuota())

    assert report.status == RunStatus.FAILED.value
    assert report.requests_made == 0
    assert "неизвестен" in report.error


async def test_unknown_and_not_enough_are_different_verdicts() -> None:
    """C6 против C7: причины лечатся по-разному, значит и коды разные.

    «Мало квоты» — ждать или поднимать лимит; «остаток неизвестен» — чинить
    доступ к Ahrefs. Один код на оба заставил бы оператора гадать.
    """
    not_enough = await preflight(FixtureQuota(left=100), needed=1000)
    unknown = await preflight(BrokenQuota(), needed=10)

    assert not_enough.verdict is QuotaVerdict.NOT_ENOUGH
    assert unknown.verdict is QuotaVerdict.UNKNOWN


async def test_soft_floor_keeps_a_reserve(monkeypatch: pytest.MonkeyPatch) -> None:
    """C6: мягкий стоп — прогон не съедает квоту до нуля.

    Заказчику нужен запас на срочный ручной запрос — иначе сервис исправно
    работает и при этом блокирует работу людей.
    """
    monkeypatch.setattr(config.ahrefs, "units_min_left", 5000)

    state = await preflight(FixtureQuota(left=10_000), needed=5_500)

    assert state.verdict is QuotaVerdict.NOT_ENOUGH


async def test_reserve_is_visible_to_the_next_estimate(db_session: AsyncSession) -> None:
    """C8: смета второго прогона видит остаток минус резерв первого.

    Без этого «кнопка неактивна при нехватке» защищает только первого
    нажавшего, а запускают шесть человек из четырёх отделов.
    """
    user = await system_user(db_session)
    running = await open_run(db_session, started_by=user.id, projects_total=1)
    await start_run(db_session, running)
    from ahrefs_cases.collect.budget import reserve

    await reserve(db_session, running.id, 9_000)
    await db_session.flush()
    await _load(db_session, 10)

    report = await collect_all(
        db_session, AhrefsFixture(), now=NOW, quota=FixtureQuota(left=10_000)
    )

    assert report.status == RunStatus.FAILED.value
    assert "зарезервировано 9000" in report.error


async def test_finished_run_releases_its_reserve(db_session: AsyncSession) -> None:
    """C8: резерв снимается сменой статуса, а не компенсирующей строкой.

    Два способа сказать одно и то же разошлись бы на первом прогоне, упавшем
    в середине: строка есть, компенсации нет, квота занята навсегда.
    """
    await _load(db_session, 5)
    await collect_all(db_session, AhrefsFixture(), now=NOW)

    assert await reserved_units(db_session) == 0
