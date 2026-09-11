"""Графики проекта по HTTP. Примеры приёмки поставки `api-charts`: E1–E8.

Главное свойство проверяется сравнением, а не глазами: рисунок, отданный по
HTTP, обязан совпадать с тем, который уходит в PDF. Два рисунка разошлись бы на
шкале или подписях, и сотрудник с клиентом увидели бы разные кривые одного
проекта.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import Group, Metric, MetricSource, UserGroup
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict

PASSWORD = "очень-длинный-пароль"
EMAIL = "charts@test.local"
WITH_VERDICT = "charts-good.example"
WITHOUT_VERDICT = "charts-plain.example"
EMPTY = "charts-empty.example"
DOMAINS = (WITH_VERDICT, WITHOUT_VERDICT, EMPTY)
MONTHS = (date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1))


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
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
        from sqlalchemy import delete, select

        ids = (
            (await session.execute(select(Project.id).where(Project.domain.in_(DOMAINS))))  # type: ignore[attr-defined]
            .scalars()
            .all()
        )
        if ids:
            await session.execute(delete(Verdict).where(Verdict.project_id.in_(ids)))  # type: ignore[attr-defined]
            await session.execute(delete(MetricPoint).where(MetricPoint.project_id.in_(ids)))  # type: ignore[attr-defined]
        await session.execute(delete(Project).where(Project.domain.in_(DOMAINS)))  # type: ignore[attr-defined]
        await session.execute(delete(User).where(User.email == EMAIL))  # type: ignore[attr-defined]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


def _points(project_id: int, source: MetricSource) -> list[MetricPoint]:
    """Ряды трафика и обеих корзин позиций: из них строятся оба графика ТЗ."""
    rows: list[MetricPoint] = []
    for index, month in enumerate(MONTHS):
        for metric, base in (
            (Metric.ORG_TRAFFIC, 1000.0),
            (Metric.KW_TOP3, 10.0),
            (Metric.KW_TOP4_10, 20.0),
        ):
            rows.append(
                MetricPoint(
                    project_id=project_id,
                    metric=metric,
                    point_date=month,
                    value=base * (index + 1),
                    source=source,
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
    return rows


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)

    async def _seed(session: object) -> None:
        from ahrefs_cases.classify.rulesets import seed_thresholds

        ruleset = await seed_thresholds(session)  # type: ignore[arg-type]
        ruleset.is_active = True
        projects = [
            Project(
                domain=domain,
                period_start=date(2025, 2, 1),
                period_end=date(2025, 4, 1),
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
        session.add_all(  # type: ignore[attr-defined]
            [
                User(
                    email=EMAIL,
                    full_name="Читатель",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.USER,
                ),
                *projects,
            ]
        )
        await session.flush()  # type: ignore[attr-defined]

        session.add_all(  # type: ignore[attr-defined]
            [
                *_points(projects[0].id, MetricSource.FIXTURE),
                *_points(projects[1].id, MetricSource.FIXTURE),
                # Третий проект намеренно без единой точки: E3.
                Verdict(
                    project_id=projects[0].id,
                    ruleset_id=ruleset.id,
                    group=Group.GOOD,
                    score=1400.0,
                    reasons={"checks": []},
                    point_a={
                        "at": "2025-02-01",
                        "months_used": 2,
                        "values": {"org_traffic": 1000.0},
                        "derived": {},
                    },
                    point_b={
                        "at": "2025-04-01",
                        "months_used": 2,
                        "values": {"org_traffic": 4000.0},
                        "derived": {},
                    },
                ),
            ]
        )

    writer(_seed)
    yield
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


def _project_id(client: TestClient, domain: str) -> int:
    rows = client.get("/api/projects", params={"query": domain}, headers=_headers(client)).json()
    return int(rows[0]["id"])


def _charts(client: TestClient, domain: str) -> list[dict[str, str]]:
    project_id = _project_id(client, domain)
    response = client.get(f"/api/projects/{project_id}/charts", headers=_headers(client))
    assert response.status_code == 200
    return list(response.json())


def test_two_charts_with_titles(client: TestClient) -> None:
    """E1: два графика ТЗ — трафик и позиции, каждый с заголовком."""
    blocks = _charts(client, WITH_VERDICT)

    assert [block["title"] for block in blocks] == [
        "Динамика органического трафика",
        "Динамика позиций",
    ]
    assert all(block["svg"].startswith("<svg") for block in blocks)


def test_web_and_pdf_draw_the_same_picture(client: TestClient) -> None:
    """E2: рисунок из HTTP совпадает с рисунком PDF **до символа**.

    Это и есть решение владельца «один SVG на оба». Сравнение, а не осмотр:
    расхождение в шкале или подписи глазами не ловится, а клиенту показывают
    именно эти кривые.
    """
    from ahrefs_cases.cases.builder import chart_series
    from ahrefs_cases.classify.points import window_from
    from ahrefs_cases.classify.series import load_series
    from ahrefs_cases.export.charts import curve_blocks
    from ahrefs_cases.storage.session import get_sessionmaker

    project_id = _project_id(client, WITH_VERDICT)
    over_http = _charts(client, WITH_VERDICT)

    async def _direct() -> list[dict[str, str]]:
        async with get_sessionmaker()() as session:
            series = await load_series(session, project_id, MetricSource.FIXTURE)
            return curve_blocks(
                chart_series(series),
                period_start=date(2025, 2, 1),
                window_a=window_from(date(2025, 2, 1), 2, forward=True),
                window_b=window_from(date(2025, 4, 1), 2, forward=False),
            )

    assert over_http == asyncio.run(_direct())


def test_project_without_series_has_no_empty_axes(client: TestClient) -> None:
    """E3: рядов нет — графиков нет. Пустые оси сказали бы «роста не было»."""
    assert _charts(client, EMPTY) == []


def test_verdict_windows_are_drawn(client: TestClient) -> None:
    """E4: полосы окон А и Б берутся из записанного вердикта (L41)."""
    traffic = _charts(client, WITH_VERDICT)[0]["svg"]

    # Полоса подписана одной буквой — так она и стоит на рисунке в PDF.
    assert ">А</text>" in traffic
    assert ">Б</text>" in traffic


def test_charts_without_verdict_keep_curves(client: TestClient) -> None:
    """E5: «плохому» проекту кейс не собирают, но кривые смотреть всё равно надо."""
    blocks = _charts(client, WITHOUT_VERDICT)

    assert blocks
    assert ">А</text>" not in blocks[0]["svg"]
    assert ">Б</text>" not in blocks[0]["svg"]


def test_missing_project_is_404(client: TestClient) -> None:
    """E6: несуществующий проект — 404 с номером, а не пустой список."""
    response = client.get("/api/projects/999999/charts", headers=_headers(client))

    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_charts_need_the_read_right(client: TestClient) -> None:
    """E7: графики закрыты тем же правом, что и карточка."""
    assert client.get("/api/projects/1/charts").status_code == 401


def test_card_reads_series_of_the_configured_source(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    writer: Callable[[Callable[..., object]], None],
) -> None:
    """E8: источник рядов выбирает **конфиг**, а не умолчание обработчика.

    Повторение L53: с умолчанием `MetricSource.FIXTURE` в сигнатуре живой режим
    читал бы фикстурные ряды и показывал пустые графики при целой базе — то
    есть сломался бы в Ф7, на боевом ключе.

    Проверяется сменой **конфига**, а не аргумента: аргумент и был тем местом,
    где предохранитель отключался.
    """
    from ahrefs_cases import config

    project_id = _project_id(client, WITHOUT_VERDICT)

    async def _relabel(session: object) -> None:
        from sqlalchemy import update

        await session.execute(  # type: ignore[attr-defined]
            update(MetricPoint)
            .where(MetricPoint.project_id == project_id)
            .values(source=MetricSource.LIVE)
        )

    writer(_relabel)
    monkeypatch.setattr(config.ahrefs, "provider", "live")
    monkeypatch.setattr(config.ahrefs, "api_key", "тестовый-ключ-не-настоящий")

    blocks = client.get(f"/api/projects/{project_id}/charts", headers=_headers(client)).json()
    card = client.get(f"/api/projects/{project_id}", headers=_headers(client)).json()

    assert blocks, "в живом режиме графики обязаны строиться по рядам live"
    assert card["series"], "карточка тоже читает ряды живого режима"
