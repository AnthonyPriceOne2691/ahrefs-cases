"""Лимит длительности прогона и его согласованность с реапером.

Repro-тест дефекта Z1: реапер добивал живой прогон, потому что его порог
подбирался независимо от того, сколько прогон может идти. На фикстурах дефект
не проявляется — задача выполняется мгновенно, — поэтому первый тест
проверяет **инвариант конфига**, а не поведение: именно он не даст дефекту
вернуться.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.runner import collect_all
from ahrefs_cases.config.ahrefs import AhrefsSettings
from ahrefs_cases.intake.accept import accept
from ahrefs_cases.intake.csv_source import parse_csv_text
from ahrefs_cases.storage._enums import RunItemOutcome, RunStatus
from ahrefs_cases.storage.models.run import RunItem

COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
NOW = date(2026, 9, 15)


def test_reaper_threshold_must_exceed_run_timeout() -> None:
    """Repro Z1: несогласованные числа не дают собрать конфиг.

    Раньше `COLLECT_RUN_STALE_SEC` = 3600 стоял рядом с прогоном, худший
    случай которого — 120 минут, и ничто их не связывало. Теперь связь
    проверяется на старте процесса: подобрать несогласованные значения молча
    больше нельзя.
    """
    with pytest.raises(ValidationError, match="строго больше"):
        AhrefsSettings(_env_file=None, run_timeout_sec=3600, run_stale_sec=3600)

    with pytest.raises(ValidationError, match="строго больше"):
        AhrefsSettings(_env_file=None, run_timeout_sec=7200, run_stale_sec=3600)


def test_defaults_leave_room_for_the_worst_run() -> None:
    """Умолчания рассчитаны на худший случай, а не взяты «на глаз».

    100 доменов ÷ 3 параллельно × (60 с × 3 попытки + 36 с backoff) = 7200 с.
    Лимит прогона обязан это покрывать, иначе штатный медленный прогон будет
    обрываться собственным предохранителем.
    """
    settings = AhrefsSettings(_env_file=None)
    worst_task = settings.timeout_sec * settings.retry_count + sum(settings.retry_backoff_sec)
    worst_run = worst_task * 100 / settings.max_parallel

    assert settings.run_timeout_sec > worst_run
    assert settings.run_stale_sec > settings.run_timeout_sec


async def test_run_stops_itself_at_the_deadline(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Прогон, упёршийся в лимит, останавливается сам и говорит об этом.

    Оставшиеся домены не запрашиваются: тратить units на прогон, который уже
    признан незавершённым, незачем. Статус `partial`, а не `done` — часть
    работы не сделана, и человек должен это видеть.
    """
    monkeypatch.setattr(config.ahrefs, "run_timeout_sec", 0)
    monkeypatch.setattr(config.ahrefs, "max_parallel", 1)
    rows = "\n".join(
        f"d{index}.example.com,2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
        for index in range(5)
    )
    await accept(db_session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))

    report = await collect_all(db_session, AhrefsFixture(), now=NOW)

    assert report.projects_aborted == 5
    assert report.requests_made == 5, "план построен, но задачи не выполнялись"
    items = (await db_session.execute(select(RunItem))).scalars().all()
    assert all(item.outcome is RunItemOutcome.SKIPPED_ABORTED for item in items)
    assert all("превысил лимит" in item.reason for item in items)
    assert report.status == RunStatus.PARTIAL.value, (
        "прогон без единой выполненной задачи не «done»"
    )


async def test_normal_run_is_not_touched_by_the_deadline(db_session: AsyncSession) -> None:
    """Обратная сторона: обычный прогон дедлайном не задет."""
    rows = "d0.example.com,2025-01-01,2026-06-30,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"
    await accept(db_session, parse_csv_text(f"{COLUMNS}\n{rows}\n", origin="test"))

    report = await collect_all(db_session, AhrefsFixture(), now=NOW)

    assert report.projects_aborted == 0
    assert report.projects_ok == 1


def test_env_example_documents_both_knobs() -> None:
    """Обе ручки описаны в `.env.example` вместе с их связью.

    Инвариант в коде спасает от несогласованных чисел, но человек, который
    правит окружение, должен узнать о связи раньше, чем упрётся в ошибку.
    """
    text = Path(".env.example").read_text(encoding="utf-8")

    assert "COLLECT_RUN_TIMEOUT_SEC" in text
    assert "COLLECT_RUN_STALE_SEC" in text
    assert "строго больше" in text


def test_first_run_fits_the_customer_budget() -> None:
    """Z4: первичный прогон обязан помещаться в бюджет заказчика.

    ТЗ называет 10 000 units на первичный прогон. По нашей модели стоимости
    шаг 1 на сотне доменов плюс шаг 2 по тридцати кандидатам стоят ≈ 9650 —
    значит неснижаемый запас в 5000 (половина бюджета) делал прогон
    невозможным: preflight отказывал бы на первом реальном запуске, а выглядело
    бы это как нехватка квоты у заказчика.

    Тест считает по тем же спекам, что и смета, поэтому он поймает и обратное:
    подорожание endpoint'ов, из-за которого прогон перестанет влезать.
    """
    from ahrefs_cases.collect.endpoints import STAGE1_SPECS
    from ahrefs_cases.collect.plan import stage2_specs

    budget = 10_000
    settings = AhrefsSettings(_env_file=None)
    stage1 = sum(spec.estimate_units() for spec in STAGE1_SPECS) * 100
    # Считаем по `stage2_specs()`, то есть по тому набору, который реально
    # уйдёт в Ahrefs. Возьми мы весь список — тест проверял бы воображаемый
    # прогон и краснел бы на endpoint'ах, которые выключены флагом.
    stage2 = sum(spec.estimate_units() for spec in stage2_specs()) * 30

    assert stage1 + stage2 + settings.units_min_left <= budget, (
        f"первичный прогон {stage1 + stage2} units + запас {settings.units_min_left} "
        f"не влезает в бюджет {budget}: preflight откажет на первом же запуске"
    )
