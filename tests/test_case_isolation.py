"""Сбой сборки одного кейса не роняет пачку (Z54).

Примеры приёмки поставки `case-build-isolated`: M91 (точка вердикта не той формы у
одного из трёх), M92 (упал рисунок PDF одного; контент-запрет — по-прежнему
`case_blocked`), M93 (упали все — архива нет, судьбы есть), M94 (сбой базы роняет
сборку, как прежде), M95 (консоль: строка «не собран …» и код 3).

M91–M93 — кнопкой «Собрать кейсы» (`POST /api/runs/cases`, очередь `inline`): прогон
читается после задачи, а не по коду ответа, и строки пишутся коммитом — приложение
ходит своими соединениями (уроки L51, L54, L85). M94 — сборкой в откатываемой
транзакции. M95 — командами консоли в своём мире (`tests/cli_world.own_world`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from tests.cli_world import own_world
from tests.owned_rows import delete_owned, isolated_ruleset

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.cases.builder import build_cases
from ahrefs_cases.classify.thresholds import load_seed
from ahrefs_cases.cli import case_commands
from ahrefs_cases.export import archive
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict
from ahrefs_cases.storage.session import get_sessionmaker

EMAIL = "isolation@test.local"
PASSWORD = "изоляция-сборки-кейсов-0810"
RULESET = "тест-изоляция-кейсов"
"""Своя версия порогов: сборка берёт вердикты действующей версии, и по чужой тест
собрал бы кейсы стенда (Z12)."""

FIRST = "iso-first.example"
SECOND = "iso-second.example"
BROKEN = "iso-broken.example"
BLOCKED = "iso-blocked.example"
DOMAINS = (FIRST, SECOND, BROKEN, BLOCKED)
BROKEN_POINT = (
    "не собран: VerdictFormatError: точка вердикта не той формы: 'derived' "
    "(первопричина — KeyError: 'derived')"
)

Write = Callable[[Callable[..., Any]], None]


@dataclass(frozen=True, slots=True)
class Seed:
    """Проект теста: «хороший» 2025 года и ряд, по которому его вердикт воспроизводится."""

    domain: str
    group: Group = Group.GOOD
    geo: str = "US"
    broken: bool = False
    """Точка Б вердикта без `derived` — форма, которой `classify` не пишет."""


def _point(at: date, traffic: float) -> dict[str, object]:
    """Точка вердикта в том виде, в каком её пишет `classify/verdicts.store`."""
    return {
        "at": at.isoformat(),
        "months_used": 2,
        "values": {"org_traffic": traffic},
        "derived": {},
    }


async def _seed(session: AsyncSession, ruleset: str, *seeds: Seed) -> None:
    """Проекты, их вердикты своей версии и фикстурный ряд: 1 000 в первом полугодии,
    2 000 во втором — точки вердикта воспроизводятся при любом окне до полугода."""
    ruleset_id = await session.scalar(select(Ruleset.id).where(Ruleset.version == ruleset))
    assert ruleset_id is not None
    for seed in seeds:
        project = Project(
            domain=seed.domain,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 1),
            niche="fintech",
            geo=seed.geo,
            service_type="seo",
            client="Acme",
            owner="i.petrov",
            publishable=True,
            notes="",
        )
        session.add(project)
        await session.flush()
        point_b = _point(date(2025, 12, 1), 2000.0)
        if seed.broken:
            del point_b["derived"]
        session.add(
            Verdict(
                project_id=project.id,
                ruleset_id=ruleset_id,
                group=seed.group,
                score=0.0,
                reasons={},
                point_a=_point(date(2025, 1, 1), 1000.0),
                point_b=point_b,
                source=MetricSource.FIXTURE,
            )
        )
        session.add_all(
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, month, 1),
                value=1000.0 if month <= 6 else 2000.0,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
            for month in range(1, 13)
        )


@pytest.fixture(scope="module")
def writer() -> Iterator[Write]:
    """Один цикл и движок на модуль — запись мимо приложения (уроки L51, L54)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Callable[..., Any]) -> None:
        async def _apply() -> None:
            async with AsyncSession(engine) as session:
                await action(session)
                await session.commit()

        loop.run_until_complete(_apply())

    try:
        yield run
    finally:
        loop.run_until_complete(engine.dispose())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


@pytest.fixture
def out_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Каталог выгрузки теста: PDF и пачка не ложатся в каталог стенда."""
    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    return tmp_path


@pytest.fixture
def world(migrated_db: None, writer: Write, out_dir: Path) -> Iterator[Callable[..., None]]:
    """Свой сотрудник и своя действующая версия порогов; проекты сеет сам тест."""

    async def _delete(session: AsyncSession) -> None:
        await delete_owned(session, domains=DOMAINS, emails=(EMAIL,))

    async def _user(session: AsyncSession) -> None:
        session.add(
            User(
                email=EMAIL,
                full_name="Изоляция",
                password_hash=security.hash_password(PASSWORD),
                group=UserGroup.USER,
            )
        )

    writer(_delete)
    undo = isolated_ruleset(writer, RULESET)
    writer(_user)

    def seed(*seeds: Seed) -> None:
        async def _apply(session: AsyncSession) -> None:
            await _seed(session, RULESET, *seeds)

        writer(_apply)

    try:
        yield seed
    finally:
        undo()
        writer(_delete)


@pytest.fixture
def client(world: Callable[..., None], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Очередь в процессе: задача сборки идёт внутри запроса кнопки."""
    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-изоляции-кейсов")
    monkeypatch.setattr(config.storage, "queue_backend", "inline")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _build_cases(client: TestClient) -> dict[str, Any]:
    """Войти, нажать «Собрать кейсы» и прочитать прогон после задачи."""
    token = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}
    run_id = client.post("/api/runs/cases", headers=headers).json()["run_id"]
    card: dict[str, Any] = client.get(f"/api/runs/{run_id}", headers=headers).json()
    return card


def _fates(card: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Судьбы проектов теста: домен → (исход, причина)."""
    return {
        fate["domain"]: (fate["outcome"], fate["reason"])
        for fate in card["fates"]
        if fate["domain"] in DOMAINS
    }


def _packed(out_dir: Path) -> set[str]:
    """PDF в пачке дня — без внутреннего списка `кейсы.csv`."""
    (pack,) = out_dir.glob("*.zip")
    with ZipFile(pack) as bundle:
        return {name for name in bundle.namelist() if name.endswith(".pdf")}


def _render_fails_for(monkeypatch: pytest.MonkeyPatch, *domains: str) -> None:
    """Рисунок PDF этих доменов падает так, как падает незнакомая ошибка рендера."""
    real = archive.render_pdf

    def flaky(case: Any, *, output_dir: Path | None = None) -> Any:
        if case.domain in domains:
            message = "рисунок упал на тесте"
            raise RuntimeError(message)
        return real(case, output_dir=output_dir)

    monkeypatch.setattr(archive, "render_pdf", flaky)


def test_one_broken_verdict_does_not_drop_the_pack(
    world: Callable[..., None], client: TestClient, out_dir: Path
) -> None:
    """M91: точка вердикта не той формы у одного из трёх — пачка из двух, у третьего «упал».

    07.10.2026 ниша «B2B» уронила так сборку целиком: прогон кейсов упал без единого
    PDF и без судеб в журнале.
    """
    world(Seed(FIRST), Seed(SECOND), Seed(BROKEN, broken=True))

    card = _build_cases(client)

    assert _fates(card) == {
        FIRST: ("ok", f"кейс собран: {FIRST} — Кейс v1.pdf"),
        SECOND: ("ok", f"кейс собран: {SECOND} — Кейс v1.pdf"),
        BROKEN: ("failed", BROKEN_POINT),
    }
    assert (card["status"], card["projects_failed"], card["error"]) == ("partial", 1, "")
    assert _packed(out_dir) == {f"{FIRST} — Кейс v1.pdf", f"{SECOND} — Кейс v1.pdf"}


def test_failed_render_drops_only_its_own_case(
    world: Callable[..., None],
    client: TestClient,
    out_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M92: упавший рисунок одного PDF — его судьба; контент-запрет остаётся запретом."""
    world(Seed(FIRST), Seed(SECOND), Seed(BLOCKED, group=Group.MEDIUM, geo="BY"))
    _render_fails_for(monkeypatch, SECOND)

    card = _build_cases(client)

    fates = _fates(card)
    assert {domain: outcome for domain, (outcome, _) in fates.items()} == {
        FIRST: "ok",
        SECOND: "failed",
        BLOCKED: "case_blocked",
    }
    assert fates[SECOND][1] == "не собран: RuntimeError: рисунок упал на тесте"
    assert "контент-запрет: гео: «BY»" in fates[BLOCKED][1]
    assert card["status"] == "partial"
    assert _packed(out_dir) == {f"{FIRST} — Кейс v1.pdf"}


def test_all_failed_cases_still_close_the_run_with_fates(
    world: Callable[..., None],
    client: TestClient,
    out_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M93: упали все — архива нет, но у каждого судьба, и прогон закрыт, а не упал."""
    world(Seed(BROKEN, broken=True), Seed(SECOND))
    _render_fails_for(monkeypatch, SECOND)

    card = _build_cases(client)

    assert _fates(card) == {
        BROKEN: ("failed", BROKEN_POINT),
        SECOND: ("failed", "не собран: RuntimeError: рисунок упал на тесте"),
    }
    assert (card["status"], card["error"], card["pack"]) == ("partial", "", False)
    assert not list(out_dir.glob("*.zip"))


async def test_database_error_still_stops_the_build(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M94: сбой базы — не сбой кейса: упавший запрос рвёт транзакцию всем следующим."""
    payload = load_seed().model_dump(mode="json") | {"version": RULESET}
    db_session.add(Ruleset(version=RULESET, payload=payload, is_active=True))
    await db_session.flush()
    await _seed(db_session, RULESET, Seed(FIRST), Seed(SECOND))

    async def lost_connection(*_: object, **__: object) -> None:
        raise OperationalError("SELECT metric_points", {}, ConnectionError("соединение оборвалось"))

    monkeypatch.setattr("ahrefs_cases.cases.builder.load_series", lost_connection)

    with pytest.raises(OperationalError):
        await build_cases(db_session, source=MetricSource.FIXTURE)


CONSOLE_RULESET = "0.0.0-case-isolation"


async def test_console_names_the_failed_case_and_exits_3(
    migrated_db: None,
    out_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M95: `show`, `pack` и `render` называют упавший кейс; `pack` и `render` — код 3.

    `render` — и упавшей сборкой, и упавшим рисунком: у второго своя ветка в команде.
    """
    async with own_world(ruleset=CONSOLE_RULESET, domains=DOMAINS):
        async with get_sessionmaker()() as session:
            await _seed(session, CONSOLE_RULESET, Seed(FIRST), Seed(BROKEN, broken=True))
            await session.commit()
        line = f"не собран {BROKEN}: VerdictFormatError: точка вердикта не той формы: 'derived'"

        shown = await case_commands.show_cases(None, None, MetricSource.FIXTURE)
        assert (shown, line in capsys.readouterr().out) == (0, True)

        packed = await case_commands.pack_cases(MetricSource.FIXTURE)
        out = capsys.readouterr().out
        assert (packed, line in out, "кейсов внутри: 1" in out) == (3, True, True)

        rendered = await case_commands.render_case(BROKEN, MetricSource.FIXTURE)
        assert (rendered, line in capsys.readouterr().err) == (3, True)

        def broken_render(*_: object, **__: object) -> None:
            message = "рисунок упал на тесте"
            raise RuntimeError(message)

        monkeypatch.setattr(case_commands, "render_pdf", broken_render)
        drawn = await case_commands.render_case(FIRST, MetricSource.FIXTURE)
        failed = f"не собран {FIRST}: RuntimeError: рисунок упал на тесте"
        assert (drawn, failed in capsys.readouterr().err) == (3, True)
