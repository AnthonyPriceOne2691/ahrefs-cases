"""Управление людьми и точечные права.

Примеры приёмки поставки `api-users`: E1 (нельзя без права), E2 (заведение и
пароль один раз), E3 (повторная почта), E4 (список), E5 (личное право выдаётся
одному), E6 (личный отзыв перекрывает групповое), E7 (последний админ),
E8 (себя не выключить), E9 (перевыпуск пароля), E10 (смена своего пароля).

Приёмы перенесены из CRM агентства (`features/auth/rbac.py`,
`features/core/services/user_service.py`) — вместе с причинами, а не как код.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.user import User

PASSWORD = "очень-длинный-пароль"
ADMIN = "chief@test.local"
CLERK = "clerk2@test.local"
MADE = "made@test.local"


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

        await session.execute(delete(User).where(User.email.in_((ADMIN, CLERK, MADE))))  # type: ignore[attr-defined]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)

    async def _seed(session: object) -> None:
        session.add_all(  # type: ignore[attr-defined]
            [
                User(
                    email=ADMIN,
                    full_name="Руководитель",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.ADMIN,
                    permissions={},
                ),
                User(
                    email=CLERK,
                    full_name="Сотрудник",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.USER,
                    permissions={},
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


def _headers(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    body = client.post("/api/auth/login", json={"email": email, "password": password}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_plain_user_may_not_manage_people(client: TestClient) -> None:
    """E1: заводить людей — право `manage_users`, у группы `user` его нет."""
    response = client.post(
        "/api/users", json={"email": MADE, "group": "user"}, headers=_headers(client, CLERK)
    )

    assert response.status_code == 403
    assert "manage_users" in response.json()["detail"]


def test_admin_creates_a_user_and_gets_the_password_once(client: TestClient) -> None:
    """E2: пароль приходит в ответе; в базе только хеш, в логе — факт."""
    response = client.post(
        "/api/users",
        json={"email": MADE, "full_name": "Новичок", "group": "user"},
        headers=_headers(client, ADMIN),
    )

    assert response.status_code == 201
    body = response.json()
    password = body["password"]
    assert len(password) >= 16
    assert (
        client.post("/api/auth/login", json={"email": MADE, "password": password}).status_code
        == 200
    )


def test_email_is_taken_once(client: TestClient) -> None:
    """E3: почта — это логин."""
    headers = _headers(client, ADMIN)
    client.post("/api/users", json={"email": MADE, "group": "user"}, headers=headers)

    second = client.post("/api/users", json={"email": MADE, "group": "user"}, headers=headers)

    assert second.status_code == 409


def test_list_shows_groups_and_personal_rights(client: TestClient) -> None:
    """E4: выданное точечно право видно строкой, а не выводится из роли."""
    rows = client.get("/api/users", headers=_headers(client, ADMIN)).json()

    by_email = {row["email"]: row for row in rows}
    assert by_email[CLERK]["group"] == "user"
    assert by_email[CLERK]["personal_rights"] == {}
    assert "edit_thresholds" not in by_email[CLERK]["rights"]


def test_personal_right_overrides_the_group_both_ways(client: TestClient) -> None:
    """E5 и E6: «этому можно, хотя он не в группе» и «этому нельзя, хотя админ».

    Приём из CRM: `user.permissions` перекрывает роль в обе стороны — иначе
    второй случай не выражается вовсе, а он встречается не реже первого.
    """
    headers = _headers(client, ADMIN)
    rows = {row["email"]: row["id"] for row in client.get("/api/users", headers=headers).json()}

    granted = client.patch(
        f"/api/users/{rows[CLERK]}",
        json={"personal_rights": {"edit_thresholds": True}},
        headers=headers,
    ).json()
    revoked = client.patch(
        f"/api/users/{rows[ADMIN]}",
        json={"personal_rights": {"edit_thresholds": False}},
        headers=headers,
    ).json()

    assert "edit_thresholds" in granted["rights"]
    assert granted["group"] == "user"
    assert "edit_thresholds" not in revoked["rights"]
    assert revoked["group"] == "admin"


def test_unknown_right_is_refused(client: TestClient) -> None:
    """Право, которого не проверяет ни один роутер, — обещание (урок L23)."""
    headers = _headers(client, ADMIN)
    rows = {row["email"]: row["id"] for row in client.get("/api/users", headers=headers).json()}

    response = client.patch(
        f"/api/users/{rows[CLERK]}", json={"personal_rights": {"летать": True}}, headers=headers
    )

    assert response.status_code == 422
    assert "летать" in response.json()["detail"]


def test_last_admin_keeps_the_group(client: TestClient) -> None:
    """E7: система без администратора не управляется (защита из CRM)."""
    headers = _headers(client, ADMIN)
    rows = {row["email"]: row["id"] for row in client.get("/api/users", headers=headers).json()}

    response = client.patch(f"/api/users/{rows[ADMIN]}", json={"group": "user"}, headers=headers)

    assert response.status_code == 409
    assert "последний администратор" in response.json()["detail"]


def test_self_deactivation_is_refused(client: TestClient) -> None:
    """E8: выключивший себя администратор запирает дверь изнутри."""
    headers = _headers(client, ADMIN)
    rows = {row["email"]: row["id"] for row in client.get("/api/users", headers=headers).json()}

    response = client.patch(f"/api/users/{rows[ADMIN]}", json={"is_active": False}, headers=headers)

    assert response.status_code == 409


def test_password_reset_invalidates_the_old_one(client: TestClient) -> None:
    """E9: перевыпуск — это не «ещё один пароль», а замена."""
    headers = _headers(client, ADMIN)
    rows = {row["email"]: row["id"] for row in client.get("/api/users", headers=headers).json()}

    issued = client.post(f"/api/users/{rows[CLERK]}/password", headers=headers).json()["password"]

    assert (
        client.post("/api/auth/login", json={"email": CLERK, "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"email": CLERK, "password": issued}).status_code == 200
    )


def test_own_password_change_needs_the_current_one(client: TestClient) -> None:
    """E10: иначе достаточно один раз увести токен, чтобы забрать учётку."""
    headers = _headers(client, CLERK)

    denied = client.post(
        "/api/auth/password",
        json={"current_password": "не тот", "new_password": "новый-длинный-пароль"},
        headers=headers,
    )
    allowed = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "новый-длинный-пароль"},
        headers=headers,
    )

    assert denied.status_code == 401
    assert allowed.status_code == 204
    assert (
        client.post(
            "/api/auth/login", json={"email": CLERK, "password": "новый-длинный-пароль"}
        ).status_code
        == 200
    )
