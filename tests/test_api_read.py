"""Читающие роутеры: проекты, кейсы, расход.

Примеры приёмки поставки `api-read`: E1 (без токена), E2 (список с группами),
E3 (фильтры), E4 (граница выдачи), E5 (карточка), E6 (нет проекта), E7 (проект
без вердикта), E8 (библиотека), E9 (скачивание), E10 (расход).

Приложение поднимается с нашим `lifespan` — иначе соединение утечёт в чужой
тест (урок L51). Данные пишутся своим движком и чистятся до и после (L8).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import Group, Metric, MetricSource, UserGroup
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict

PASSWORD = "очень-длинный-пароль"
EMAIL = "reader@test.local"
DOMAINS = ("alpha.example", "beta.example")


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
    """Один цикл и один движок на модуль — для записи мимо приложения.

    Тесты API пишут данные своей сессией: приложение ходит в ту же базу, но в
    своём цикле. Прежний вариант поднимал движок на каждый вызов, и закрытые
    соединения всплывали `ResourceWarning`ом **в случайном** тесте — при
    `filterwarnings = ["error"]` это падение там, где ничего не ломали (L51).
    Один долгоживущий цикл делает закрытие детерминированным.
    """
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


def _cleanup(write: Callable[[Callable[..., object]], None]) -> None:
    async def _delete(session: object) -> None:
        from sqlalchemy import delete

        for model in (CaseArtifact, Case, Verdict, MetricPoint):
            await session.execute(delete(model))  # type: ignore[attr-defined]
        await session.execute(delete(Project).where(Project.domain.in_(DOMAINS)))  # type: ignore[attr-defined]
        await session.execute(delete(User).where(User.email == EMAIL))  # type: ignore[attr-defined]


    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


@pytest.fixture
def seeded(
    migrated_db: None,
    tmp_path: Path,
    writer: Callable[[Callable[..., object]], None],
) -> Iterator[dict[str, int]]:
    """Два проекта: у первого вердикт `good` и кейс, у второго вердикта нет."""
    _cleanup(writer)
    ids: dict[str, int] = {}
    artifact_path = tmp_path / "alpha.example — Кейс.pdf"
    artifact_path.write_bytes("%PDF-1.7 тест".encode())

    async def _seed(session: object) -> None:
        from ahrefs_cases.classify.rulesets import seed_thresholds

        # Берём засеянную версию, а не свою: выключать чужую активность значит
        # оставить дев-базу без активных порогов следующему модулю (урок L8).
        ruleset = await seed_thresholds(session)  # type: ignore[arg-type]
        # Дев-база живёт между прогонами: активность могли выключить раньше.
        ruleset.is_active = True
        user = User(
            email=EMAIL,
            full_name="Читатель",
            password_hash=security.hash_password(PASSWORD),
            group=UserGroup.USER,
        )
        projects = [
            Project(
                domain=domain,
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 1),
                niche="fintech",
                geo="US",
                service_type="seo",
                client="Acme",
                owner="i.petrov",
                publishable=True,
                notes="",
            )
            for domain in DOMAINS
        ]
        session.add_all([user, *projects])  # type: ignore[attr-defined]
        await session.flush()  # type: ignore[attr-defined]

        verdict = Verdict(
            project_id=projects[0].id,
            ruleset_id=ruleset.id,
            group=Group.GOOD,
            score=1400.0,
            reasons={
                "checks": [
                    {
                        "subject": "org_traffic",
                        "fact": 140.0,
                        "threshold": 50.0,
                        "passed": True,
                        "decisive": True,
                        "note": "рост выше порога",
                    }
                ]
            },
            point_a={"values": {"org_traffic": 1000.0}, "derived": {"kw_top10": 10.0}},
            point_b={"values": {"org_traffic": 2400.0}, "derived": {"kw_top10": 25.0}},
        )
        session.add_all(  # type: ignore[attr-defined]
            [
                verdict,
                MetricPoint(
                    project_id=projects[0].id,
                    metric=Metric.ORG_TRAFFIC,
                    point_date=date(2025, 1, 1),
                    value=1000.0,
                    source=MetricSource.FIXTURE,
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        await session.flush()  # type: ignore[attr-defined]

        case = Case(
            project_id=projects[0].id,
            verdict_id=verdict.id,
            version=1,
            anonymized=False,
            highlights={"picked": []},
            narrative="Текст кейса.",
        )
        session.add(case)  # type: ignore[attr-defined]
        await session.flush()  # type: ignore[attr-defined]
        session.add(  # type: ignore[attr-defined]
            CaseArtifact(
                case_id=case.id,
                fmt="PDF",
                path=str(artifact_path),
                filename=artifact_path.name,
                checksum="0" * 64,
                built_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        ids["project"] = projects[0].id
        ids["no_verdict"] = projects[1].id
        ids["case"] = case.id

    writer(_seed)
    yield ids
    _cleanup(writer)


@pytest.fixture
def client(seeded: dict[str, int]) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _token(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_projects_need_a_token(client: TestClient) -> None:
    """E1: читающий роутер закрыт тем же правом, что и всё остальное."""
    assert client.get("/api/projects").status_code == 401


def test_projects_list_shows_groups(client: TestClient) -> None:
    """E2 и E7: у классифицированного группа есть, у второго — `null`."""
    rows = client.get("/api/projects", headers=_token(client)).json()

    by_domain = {row["domain"]: row for row in rows}
    assert by_domain["alpha.example"]["group"] == "good"
    assert by_domain["beta.example"]["group"] is None


def test_filters_narrow_the_list(client: TestClient, seeded: dict[str, int]) -> None:
    """E3: фильтр по группе и поиск по домену."""
    headers = _token(client)

    only_good = client.get("/api/projects", params={"group": "good"}, headers=headers).json()
    by_query = client.get("/api/projects", params={"query": "beta"}, headers=headers).json()

    assert [row["domain"] for row in only_good] == ["alpha.example"]
    assert [row["domain"] for row in by_query] == ["beta.example"]


def test_limit_above_the_ceiling_is_refused(client: TestClient) -> None:
    """E4: граница выдачи не обходится параметром."""
    response = client.get("/api/projects", params={"limit": 1000}, headers=_token(client))

    assert response.status_code == 422


def test_card_shows_verdict_points_and_series(client: TestClient, seeded: dict[str, int]) -> None:
    """E5: карточка отвечает тем же, по чему принято решение (урок L41)."""
    card = client.get(f"/api/projects/{seeded['project']}", headers=_token(client)).json()

    assert card["verdict"]["group"] == "good"
    assert card["verdict"]["reasons"][0]["subject"] == "org_traffic"
    assert card["verdict"]["point_b"]["org_traffic"] == 2400.0
    assert card["verdict"]["point_b"]["kw_top10"] == 25.0
    assert card["series"][0]["metric"] == "org_traffic"


def test_missing_project_is_404(client: TestClient) -> None:
    """E6: пустая карточка выглядела бы как «проект без данных»."""
    assert client.get("/api/projects/999999", headers=_token(client)).status_code == 404


def test_case_library_and_download(client: TestClient, seeded: dict[str, int]) -> None:
    """E8 и E9: библиотека и файл под тем же именем, что уйдёт клиенту."""
    headers = _token(client)
    rows = client.get("/api/cases", headers=headers).json()
    assert rows[0]["domain"] == "alpha.example"
    assert rows[0]["filename"].endswith("Кейс.pdf")

    downloaded = client.get(f"/api/cases/{seeded['case']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")


def test_download_without_file_is_404(
    client: TestClient,
    seeded: dict[str, int],
    writer: Callable[[Callable[..., object]], None],
) -> None:
    """E9: путь в базе есть, файла на диске нет — это 404 (урок L1)."""

    async def _break_path(session: object) -> None:
        from sqlalchemy import update

        await session.execute(  # type: ignore[attr-defined]
            update(CaseArtifact).values(path="/нет/такого/файла.pdf")
        )

    writer(_break_path)

    response = client.get(f"/api/cases/{seeded['case']}/download", headers=_token(client))
    assert response.status_code == 404


def test_usage_reports_spend_and_remaining(client: TestClient) -> None:
    """E10: потрачено, зарезервировано и остаток одним ответом."""
    body = client.get("/api/usage", headers=_token(client)).json()

    assert body["spent"] >= 0
    assert body["reserved"] >= 0
    assert body["remaining"] == 10_000  # fixture-остаток: бюджет первичного прогона
