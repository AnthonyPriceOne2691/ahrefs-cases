"""Журнал сборки кейсов и оповещение о пачке говорят правду.

Примеры приёмки поставки `cases-stage-journal` (Z46): Y1 (счётчики и судьба
каждого проекта), Y2 (причины словами), Y3 (совет — ряды вердикта), Y7
(оповещение называет пачку и число кейсов), Y8 (нет пачки — нет «готово»), Y9
(пачка с кейсом удалённого проекта готовой не называется). Y4 — в
`test_cases_builder.py`, Y5 — в `test_collect_run.py`, Y6 — на экране.

Сборка идёт кнопкой — `POST /api/runs/cases`, очередь `inline`, — а прогон
проверяется после задачи, а не по коду ответа (урок L85). Приложение ходит
своими соединениями, поэтому тест пишет свои строки с коммитом, берёт свою
версию порогов и убирает за собой (уроки L68, L79, Z12).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from tests.owned_rows import delete_owned, isolated_ruleset

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage._enums import Group, Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict

EMAIL = "journal@test.local"
PASSWORD = "журнал-сборки-кейсов-2409"
RULESET = "тест-журнал-кейсов"
"""Своя версия порогов: сборка берёт вердикты действующей версии, и по чужой
тест собрал бы кейсы стенда."""

GOOD = "journal-good.example"
POOR = "journal-poor.example"
THIN = "journal-thin.example"
LIVE = "journal-live.example"
BLOCKED = "journal-blocked.example"
NEW = "journal-new.example"
DOMAINS = (GOOD, POOR, THIN, LIVE, BLOCKED, NEW)

Write = Callable[[Callable[..., object]], None]


@pytest.fixture(scope="module")
def writer() -> Iterator[Write]:
    """Один цикл и движок на модуль — запись мимо приложения (уроки L51, L54)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from ahrefs_cases import config

    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Callable[..., object]) -> None:
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


def _cleanup(write: Write) -> None:
    async def _delete(session: object) -> None:
        await delete_owned(session, domains=DOMAINS, emails=(EMAIL,))  # type: ignore[arg-type]

    write(_delete)


@pytest.fixture(autouse=True)
def app_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Очередь в процессе, свой секрет подписи и свой каталог выгрузки."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи-журнала")
    monkeypatch.setattr(config.storage, "queue_backend", "inline")
    monkeypatch.setattr(config.export, "output_dir", tmp_path)


def _point(at: date, traffic: float) -> dict[str, object]:
    """Точка вердикта в том виде, в каком её пишет `classify/verdicts.store`."""
    return {
        "at": at.isoformat(),
        "months_used": 2,
        "values": {"org_traffic": traffic},
        "derived": {},
    }


async def _project(
    session: object,
    ruleset_id: int,
    domain: str,
    group: Group | None,
    *,
    verdict_source: MetricSource = MetricSource.FIXTURE,
    geo: str = "US",
) -> None:
    """Проект 2025 года; вердикт своей версии и фикстурный ряд, по которому он
    воспроизводится (1 000 в первом полугодии, 2 000 во втором). `group=None` —
    вердикта нет вовсе."""
    project = Project(
        domain=domain,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 1),
        niche="fintech",
        geo=geo,
        service_type="seo",
        client="Acme",
        owner="i.petrov",
        publishable=True,
        notes="",
    )
    session.add(project)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    if group is None:
        return
    session.add(  # type: ignore[attr-defined]
        Verdict(
            project_id=project.id,
            ruleset_id=ruleset_id,
            group=group,
            score=0.0,
            reasons={},
            point_a=_point(date(2025, 1, 1), 1000.0),
            point_b=_point(date(2025, 12, 1), 2000.0),
            source=verdict_source,
        )
    )
    session.add_all(  # type: ignore[attr-defined]
        [
            MetricPoint(
                project_id=project.id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, month, 1),
                value=1000.0 if month <= 6 else 2000.0,
                source=MetricSource.FIXTURE,
                fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
            for month in range(1, 13)
        ]
    )


@pytest.fixture
def seeded(migrated_db: None, writer: Write) -> Iterator[None]:
    """Шесть своих проектов — по одному на каждый исход сборки — и свой сотрудник."""
    _cleanup(writer)
    undo = isolated_ruleset(writer, RULESET)

    async def _seed(session: object) -> None:
        session.add(  # type: ignore[attr-defined]
            User(
                email=EMAIL,
                full_name="Журнал",
                password_hash=security.hash_password(PASSWORD),
                group=UserGroup.USER,
            )
        )
        ruleset_id = await session.scalar(  # type: ignore[attr-defined]
            select(Ruleset.id).where(Ruleset.version == RULESET)
        )
        await _project(session, ruleset_id, GOOD, Group.GOOD)
        await _project(session, ruleset_id, POOR, Group.POOR)
        await _project(session, ruleset_id, THIN, Group.INSUFFICIENT_DATA)
        await _project(session, ruleset_id, LIVE, Group.GOOD, verdict_source=MetricSource.LIVE)
        await _project(session, ruleset_id, BLOCKED, Group.MEDIUM, geo="BY")
        await _project(session, ruleset_id, NEW, None)

    writer(_seed)
    yield
    undo()
    _cleanup(writer)


@pytest.fixture
def client(seeded: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _build_cases(client: TestClient, headers: dict[str, str]) -> dict:
    """Нажать «Собрать кейсы» и прочитать прогон после задачи."""
    run_id = client.post("/api/runs/cases", headers=headers).json()["run_id"]
    return client.get(f"/api/runs/{run_id}", headers=headers).json()


def _projects_in_base(write: Write) -> int:
    found: list[int] = []

    async def _count(session: object) -> None:
        found.append(int(await session.scalar(select(func.count()).select_from(Project))))  # type: ignore[attr-defined]

    write(_count)
    return found[0]


def _mine(card: dict) -> dict[str, dict]:
    return {fate["domain"]: fate for fate in card["fates"] if fate["domain"] in DOMAINS}


def test_cases_run_counts_and_names_every_project(client: TestClient, writer: Write) -> None:
    """Y1: «собрано» — кейсы в пачке, и у каждого проекта своя судьба.

    На проде 24.09.2026 журнал сказал «0 из 53, пропущено 53» при десяти
    собранных кейсах, а раскрытие — «записей по доменам нет»: сводка сборки
    дошла только до лога воркера.
    """
    card = _build_cases(client, _headers(client))

    assert card["status"] == "done"
    assert card["projects_ok"] == 1, "собран один кейс — journal-good.example"
    assert card["projects_total"] == _projects_in_base(writer)
    assert card["projects_skipped"] == card["projects_total"] - 1
    assert {domain: fate["outcome"] for domain, fate in _mine(card).items()} == {
        GOOD: "ok",
        POOR: "case_not_eligible",
        THIN: "case_insufficient_data",
        LIVE: "case_verdict_mismatch",
        BLOCKED: "case_blocked",
        NEW: "case_no_verdict",
    }


def test_fates_say_why_in_words(client: TestClient) -> None:
    """Y2: причина у каждой судьбы — словами, с тем, что делать дальше."""
    reasons = {
        domain: fate["reason"]
        for domain, fate in _mine(_build_cases(client, _headers(client))).items()
    }

    assert reasons[GOOD] == f"кейс собран: {GOOD} — Кейс v1.pdf"
    assert "«плохой»" in reasons[POOR] and "хорошим и средним" in reasons[POOR]
    assert "«данных не хватает»" in reasons[THIN] and "карточке проекта" in reasons[THIN]
    assert "контент-запрет: гео: «BY»" in reasons[BLOCKED]
    assert f"«{RULESET}»" in reasons[NEW]


def test_mismatch_advice_names_the_verdicts_rows(client: TestClient) -> None:
    """Y3: совет — пересчёт по рядам вердикта, а не по текущему режиму.

    Прежний совет «перезапустите classify по этому источнику» читался как
    «по режиму провайдера»: на проде в `fixture` такой пересчёт переписал бы
    живые вердикты фикстурными.
    """
    reason = _mine(_build_cases(client, _headers(client)))[LIVE]["reason"]

    assert "вердикт вынесен по рядам «live», а показаны «fixture»" in reason
    assert "переклассифицируйте по рядам «live»" in reason
    assert "`classify --source live`" in reason
    assert "--source fixture" not in reason


def _cases_alerts(client: TestClient, headers: dict[str, str]) -> list[dict]:
    found = client.get("/api/alerts", headers=headers).json()
    return [item for item in found if item["kind"].startswith("cases_")]


def test_alert_names_the_pack_and_its_size(client: TestClient, tmp_path: Path) -> None:
    """Y7: «готова пачка» — имя архива и число кейсов в нём, а не один PDF."""
    headers = _headers(client)
    _build_cases(client, headers)
    pack = next(tmp_path.glob("*.zip"))

    alerts = _cases_alerts(client, headers)

    assert alerts == [
        {
            "kind": "cases_ready",
            "severity": "good",
            "message": f"готова пачка кейсов «{pack.name}»: кейсов внутри — 1 "
            "— проверьте перед публикацией",
        }
    ]


def test_no_pack_means_no_ready_alert(client: TestClient, tmp_path: Path) -> None:
    """Y8: артефакты кейсов в базе есть, пачки нет — «готово» не говорится.

    Прежде оповещение называло самый свежий PDF («готов кейс …»), даже когда
    сборка не положила в каталог выгрузки ни одного архива.
    """
    headers = _headers(client)
    _build_cases(client, headers)
    for pack in tmp_path.glob("*.zip"):
        pack.unlink()

    assert _cases_alerts(client, headers) == []


def test_pack_with_a_deleted_case_is_not_ready(client: TestClient, tmp_path: Path) -> None:
    """Y9: пачка с PDF, чьей суммы нет ни у одного артефакта, не «готова»."""
    from ahrefs_cases.api.routers.cases import PACK_OF_DELETED

    with ZipFile(tmp_path / "кейсы-2026-09-24.zip", "w") as bundle:
        bundle.writestr("удалённый.example — Кейс v1.pdf", b"%PDF-1.7 not a case of any project")

    alerts = _cases_alerts(client, _headers(client))

    assert alerts == [
        {
            "kind": "cases_pack_blocked",
            "severity": "warning",
            "message": f"пачка кейсов «кейсы-2026-09-24.zip» не отдаётся: {PACK_OF_DELETED}",
        }
    ]
