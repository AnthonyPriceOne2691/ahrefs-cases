"""Команды консоли исполнением в процессе (Z22). Примеры приёмки: M71–M77.

Покрытие трёх файлов CLI стояло ниже цели 70 %: тесты `test_cli_exit_codes` гоняют
скрипт подпроцессом и трогают только ранний выход по нечитаемому источнику. Здесь —
что команды говорят человеку и какой код возвращают, на настоящей базе и фикстурном
провайдере. Строки — коммитом и со своей версией порогов (`tests/cli_world.py`).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import func, select
from tests.cli_world import own_world

from ahrefs_cases import config
from ahrefs_cases.cli import case_commands, collect_commands, source
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.verdict import Verdict
from ahrefs_cases.storage.session import get_sessionmaker

DOMAIN = "cli-commands.example"
OTHER = "cli-commands-b.example"
MISSING = "cli-missing.example"
RULESET = "0.0.0-cli-commands"
COLUMNS = (
    "domain,period_start,period_end,niche,geo,service_type,"
    "work_volume,client,owner,publishable,target_mode,notes"
)
EXIT_BAD_SOURCE = 2
EXIT_RUN_FAILED = 3
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_collect.py"


@pytest.fixture
async def world(migrated_db: None) -> AsyncIterator[None]:
    async with own_world(ruleset=RULESET, domains=(DOMAIN, OTHER)):
        yield


@pytest.fixture
def out_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Каталог выгрузки теста: PDF и пачка не ложатся в каталог стенда."""
    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    return tmp_path


def _script() -> ModuleType:
    """Скрипт консоли как модуль: его `_main` переводит исключения в коды возврата."""
    spec = importlib.util.spec_from_file_location("run_collect_in_process", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _list(path: Path, *rows: str) -> str:
    path.write_text("\n".join([COLUMNS, *rows]) + "\n", encoding="utf-8")
    return str(path)


def _row(domain: str, start: str = "2025-01-01") -> str:
    return f"{domain},{start},2025-12-31,fintech,US,seo,10,Acme,i.petrov,yes,subdomains,"


async def _campaign(start: date, *, group: Group | None, traffic: tuple[float, float]) -> int:
    """Кампания сайта теста: проект, ряд трафика по своей версии порогов и вердикт.

    Ряд постоянен в каждой половине года — точки вердикта воспроизводятся по нему при
    окнах версии теста, и сверка чисел кейс не останавливает (как в `test_cases_pack`).
    """
    async with get_sessionmaker()() as session:
        ruleset = await session.scalar(select(Ruleset.id).where(Ruleset.version == RULESET))
        assert ruleset is not None
        project = Project(
            domain=DOMAIN,
            period_start=start,
            period_end=date(start.year, 12, 1),
            niche="fintech",
            geo="US",
            service_type="seo",
            client="Acme",
            owner="i.petrov",
            publishable=True,
            notes="",
        )
        session.add(project)
        await session.flush()
        before, after = traffic
        session.add_all(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(start.year, month, 1),
                value=before if month <= 6 else after,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
            for month in range(1, 13)
        )
        if group is not None:
            session.add(
                Verdict(
                    project_id=project.id,
                    ruleset_id=ruleset,
                    group=group,
                    point_a=_point(start, before),
                    point_b=_point(date(start.year, 12, 1), after),
                    source=MetricSource.FIXTURE,
                )
            )
        await session.commit()
        return project.id


def _point(at: date, traffic: float) -> dict[str, object]:
    """Точка вердикта в том виде, в каком её пишет `classify/verdicts.store`."""
    return {
        "at": at.isoformat(),
        "months_used": 2,
        "values": {"org_traffic": traffic},
        "derived": {},
    }


async def _runs() -> int:
    async with get_sessionmaker()() as session:
        return int(await session.scalar(select(func.count()).select_from(Run)) or 0)


@pytest.mark.usefixtures("world")
async def test_intake_reports_what_it_took(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M71: годный список — код 0 и «принято: 2»; брак во всех строках — код 1 и причины."""
    good = _list(tmp_path / "good.csv", _row(DOMAIN), _row(OTHER))
    broken = _list(tmp_path / "broken.csv", _row(DOMAIN, "не дата"), _row(OTHER, "не дата"))

    assert await collect_commands._intake(good) == 0
    assert "принято: 2 (создано 2, обновлено 0)" in capsys.readouterr().out
    assert await collect_commands._intake(broken) == 1
    told = capsys.readouterr().out
    assert "принято: 0" in told
    assert told.count(": period_start — ") == 2


@pytest.mark.usefixtures("world")
async def test_collect_names_the_domain_missing_from_the_base(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """M72: домена нет в базе — код 3 и его имя; прогон не открыт."""
    before = await _runs()
    args = argparse.Namespace(command="collect", refresh=False, only=MISSING)

    code = await _script()._main(args)

    assert code == EXIT_RUN_FAILED
    assert f"в базе нет проектов: {MISSING}" in capsys.readouterr().err
    assert await _runs() == before


@pytest.mark.usefixtures("world")
async def test_paying_steps_without_work_buy_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """M73: без кандидатов шаг 2 и без «хороших» данные под кейс ничего не покупают."""
    await _campaign(date(2025, 1, 1), group=None, traffic=(0.0, 0.0))
    before = await _runs()

    assert await collect_commands._stage2(only=[DOMAIN]) == 0
    assert await collect_commands._case_data(only=[DOMAIN]) == 0

    told = capsys.readouterr().out
    assert "кандидатов нет: шаг 2 не нужен" in told
    assert "кейсов нет: «хороших» и «средних» по действующим порогам не найдено" in told
    assert await _runs() == before


@pytest.mark.usefixtures("world")
async def test_thresholds_commands_answer_in_words(capsys: pytest.CaptureFixture[str]) -> None:
    """M74: классификация — код 0; неизвестная версия порогов — код 2 и причина."""
    await _campaign(date(2025, 1, 1), group=None, traffic=(1000.0, 2000.0))

    assert await collect_commands._classify(MetricSource.FIXTURE) == 0
    assert await collect_commands._recalc(RULESET, make_active=False) == 0
    assert await collect_commands._preview(RULESET) == 0
    capsys.readouterr()
    assert await collect_commands._recalc("нет-такой", make_active=True) == EXIT_BAD_SOURCE
    assert await collect_commands._preview("нет-такой") == EXIT_BAD_SOURCE

    told = capsys.readouterr().err
    assert "пересчёт не выполнен: " in told
    assert "предпросмотр не выполнен: " in told


@pytest.mark.usefixtures("world")
async def test_diagnose_and_explain_name_every_campaign(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """M75: незнакомый домен — код 2; без «плохих» — сказано; две кампании — обе с условиями."""
    await _campaign(date(2024, 1, 1), group=Group.POOR, traffic=(2000.0, 500.0))
    await _campaign(date(2025, 1, 1), group=None, traffic=(1000.0, 2000.0))

    assert await collect_commands._diagnose(MISSING) == EXIT_BAD_SOURCE
    assert f"проект не найден: {MISSING}" in capsys.readouterr().err
    assert await collect_commands._diagnose(DOMAIN) == 0
    assert "кампаний по домену: 2" in capsys.readouterr().out
    assert await collect_commands._diagnose(None) == 0
    assert "«плохих» проектов: 1" in capsys.readouterr().out
    assert await collect_commands._explain(DOMAIN) == 0

    told = capsys.readouterr().out
    assert f"кампаний по домену {DOMAIN}: 2" in told
    assert "✓" in told
    assert "✗" in told


@pytest.mark.usefixtures("world")
async def test_diagnose_without_poor_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    """M75: «плохих» по действующей версии нет — так и сказано, код 0."""
    assert await collect_commands._diagnose(None) == 0
    assert "«плохих» проектов нет — диагностировать нечего" in capsys.readouterr().out


@pytest.mark.usefixtures("world")
async def test_case_commands_show_render_and_pack(
    out_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """M76: «хороший» с рядом — кейс с числами в выводе, PDF на диске, архив собран."""
    await _campaign(date(2025, 1, 1), group=Group.GOOD, traffic=(1000.0, 2000.0))

    assert await case_commands.show_cases(DOMAIN, None, MetricSource.FIXTURE) == 0
    shown = capsys.readouterr().out
    assert f"{DOMAIN} — good, " in shown
    assert "1000 →       2000" in shown
    assert await case_commands.render_case(DOMAIN, MetricSource.FIXTURE) == 0
    rendered = capsys.readouterr().out
    assert f"{DOMAIN} → {out_dir}" in rendered
    assert "версия кейса 1" in rendered
    assert await case_commands.pack_cases(MetricSource.FIXTURE) == 0
    packed = capsys.readouterr().out
    assert str(out_dir) in packed
    assert ".zip" in packed


@pytest.mark.usefixtures("world", "out_dir")
async def test_case_commands_without_cases_say_why(capsys: pytest.CaptureFixture[str]) -> None:
    """M76: незнакомый домен у `render` — код 2; пачка без кейсов — код 2 и причина."""
    assert await case_commands.render_case(MISSING, MetricSource.FIXTURE) == EXIT_BAD_SOURCE
    assert f"проект не найден: {MISSING}" in capsys.readouterr().err
    assert await case_commands.pack_cases(MetricSource.FIXTURE) == EXIT_BAD_SOURCE
    assert capsys.readouterr().err.strip()


def test_named_source_wins_over_the_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """M77: `--source live` читает живые ряды в режиме fixture; без флага — режим провайдера."""
    monkeypatch.setattr(config.ahrefs, "provider", "fixture")
    assert source.named(argparse.Namespace(source="live")) is MetricSource.LIVE
    assert source.named(argparse.Namespace(source="fixture")) is MetricSource.FIXTURE
    assert source.named(argparse.Namespace()) is None
    assert source.reading_source(None) is MetricSource.FIXTURE
    monkeypatch.setattr(config.ahrefs, "provider", "live")
    assert source.reading_source(None) is MetricSource.LIVE
