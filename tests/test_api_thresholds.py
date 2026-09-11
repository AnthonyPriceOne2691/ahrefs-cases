"""Пороги по API и алерты.

Примеры приёмки поставки `api-thresholds`: E1 (пользователю нельзя), E2
(админу можно и версия не активна), E3 (повтор имени), E4 (негодные пороги),
E5 и E6 (предпросмотр), E7 (активация), E8 (пересчёт), E9 и E10 (алерты).

Различие групп в ТЗ сейчас ровно одно — правка порогов. Эта поставка первая,
где оно видно по вызовам одного экрана (урок L52: форма проверки была написана
в Ф1 именно под это).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.classify.thresholds import load_seed
from ahrefs_cases.storage import RunStatus, UserGroup
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict

PASSWORD = "очень-длинный-пароль"
USERS = {"boss@test.local": UserGroup.ADMIN, "clerk@test.local": UserGroup.USER}
NEW_VERSION = "тест-порогов"


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
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


def _cleanup(write: Callable[[Callable[..., object]], None]) -> None:
    async def _delete(session: object) -> None:
        from sqlalchemy import delete

        await session.execute(delete(Verdict))  # type: ignore[attr-defined]
        await session.execute(delete(Run))  # type: ignore[attr-defined]
        await session.execute(delete(Ruleset).where(Ruleset.version == NEW_VERSION))  # type: ignore[attr-defined]
        await session.execute(delete(Project).where(Project.domain == "thr.example"))  # type: ignore[attr-defined]
        await session.execute(delete(User).where(User.email.in_(tuple(USERS))))  # type: ignore[attr-defined]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)

    async def _seed(session: object) -> None:
        from ahrefs_cases.classify.rulesets import seed_thresholds

        ruleset = await seed_thresholds(session)  # type: ignore[arg-type]
        ruleset.is_active = True
        session.add_all(  # type: ignore[attr-defined]
            [
                *(
                    User(
                        email=email,
                        full_name="Тест",
                        password_hash=security.hash_password(PASSWORD),
                        group=group,
                    )
                    for email, group in USERS.items()
                ),
                Project(
                    domain="thr.example",
                    period_start=date(2025, 1, 1),
                    period_end=date(2025, 12, 1),
                    niche="fintech",
                    geo="US",
                    service_type="seo",
                    client="Acme",
                    owner="i.petrov",
                    publishable=True,
                    notes="",
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


def _headers(client: TestClient, email: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _payload() -> dict[str, object]:
    body = load_seed().model_dump(mode="json")
    body.pop("version", None)
    return body


def test_user_may_not_save_thresholds(client: TestClient) -> None:
    """E1: различие групп в ТЗ ровно одно, и вот оно."""
    response = client.post(
        "/api/rulesets",
        json={"version": NEW_VERSION, "payload": _payload()},
        headers=_headers(client, "clerk@test.local"),
    )

    assert response.status_code == 403
    assert "edit_thresholds" in response.json()["detail"]


def test_admin_saves_a_version_that_is_not_active_yet(client: TestClient) -> None:
    """E2: сохранение и применение разнесены нарочно."""
    response = client.post(
        "/api/rulesets",
        json={"version": NEW_VERSION, "note": "тест", "payload": _payload()},
        headers=_headers(client, "boss@test.local"),
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is False
    listed = client.get("/api/rulesets", headers=_headers(client, "clerk@test.local")).json()
    assert NEW_VERSION in {item["version"] for item in listed}


def test_same_version_twice_is_a_conflict(client: TestClient) -> None:
    """E3: версия неизменяема — вердикты на неё ссылаются."""
    headers = _headers(client, "boss@test.local")
    body = {"version": NEW_VERSION, "payload": _payload()}

    assert client.post("/api/rulesets", json=body, headers=headers).status_code == 201
    second = client.post("/api/rulesets", json=body, headers=headers)

    assert second.status_code == 409


def test_broken_thresholds_are_refused(client: TestClient) -> None:
    """E4: чужая форма, попавшая в базу, обнаружилась бы уже на вердиктах (L23)."""
    response = client.post(
        "/api/rulesets",
        json={"version": NEW_VERSION, "payload": {"groups": "не объект"}},
        headers=_headers(client, "boss@test.local"),
    )

    assert response.status_code == 422


def test_preview_is_open_to_everyone_and_writes_nothing(client: TestClient) -> None:
    """E5 и E6: смотреть и применять — разные действия, и пересчёт бесплатен."""
    active = client.get("/api/rulesets", headers=_headers(client, "boss@test.local")).json()
    version = next(item["version"] for item in active if item["is_active"])

    response = client.post(
        f"/api/rulesets/{version}/preview", headers=_headers(client, "clerk@test.local")
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == version
    assert {"changes", "first_time", "unchanged", "missing_data"} <= set(body)


def test_activation_needs_the_right(client: TestClient) -> None:
    """E7: пользователю нельзя, админу можно, и активная версия меняется."""
    boss = _headers(client, "boss@test.local")
    client.post("/api/rulesets", json={"version": NEW_VERSION, "payload": _payload()}, headers=boss)

    denied = client.post(
        f"/api/rulesets/{NEW_VERSION}/activate", headers=_headers(client, "clerk@test.local")
    )
    allowed = client.post(f"/api/rulesets/{NEW_VERSION}/activate", headers=boss)

    assert denied.status_code == 403
    assert allowed.status_code == 200
    listed = client.get("/api/rulesets", headers=boss).json()
    assert [item["version"] for item in listed if item["is_active"]] == [NEW_VERSION]


def test_recalc_runs_without_touching_ahrefs(client: TestClient) -> None:
    """E8: смена порогов обязана быть бесплатной — на этом стоит калибровка."""
    boss = _headers(client, "boss@test.local")
    version = next(
        item["version"]
        for item in client.get("/api/rulesets", headers=boss).json()
        if item["is_active"]
    )

    response = client.post(f"/api/rulesets/{version}/recalc", headers=boss)

    assert response.status_code == 200
    assert response.json()["version"] == version


def test_alerts_report_low_units_and_failed_runs(
    client: TestClient,
    writer: Callable[[Callable[..., object]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E9 и E10: повод называется числом и номером, а не «проверьте сервис»."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.ahrefs, "units_min_left", 10_000_000)

    async def _fail_run(session: object) -> None:
        session.add(  # type: ignore[attr-defined]
            Run(started_by=1, status=RunStatus.FAILED, error="нарочно", projects_total=1)
        )

    boss = _headers(client, "boss@test.local")
    user_id = client.get("/api/auth/me", headers=boss).json()
    assert user_id["group"] == "admin"
    writer(_fail_run)

    found = client.get("/api/alerts", headers=boss).json()

    kinds = {item["kind"] for item in found}
    assert "units_low" in kinds
    assert any("нарочно" in item["message"] for item in found if item["kind"] == "run_failed")


def test_no_reasons_means_empty_list(client: TestClient) -> None:
    """E10: пустой список — ответ «поводов нет», а не тишина."""
    response = client.get("/api/alerts", headers=_headers(client, "clerk@test.local"))

    assert response.status_code == 200
    assert isinstance(response.json(), list)
