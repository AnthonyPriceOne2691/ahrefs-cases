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
SECOND_ADMIN = "second-admin@test.local"


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
        from sqlalchemy import delete, select

        # Прогоны своих людей — прежде самих людей: `runs.started_by` стоит с
        # `ON DELETE RESTRICT`, и уборка упала бы на учётке, за которой тест
        # оставил прогон. Чужих прогонов это не трогает: только свои почты.
        from ahrefs_cases.storage.models.run import Run as _Run

        mine = select(User.id).where(User.email.in_((ADMIN, CLERK, MADE, SECOND_ADMIN)))
        await session.execute(delete(_Run).where(_Run.started_by.in_(mine)))  # type: ignore[attr-defined]
        await session.execute(  # type: ignore[attr-defined]
            delete(User).where(User.email.in_((ADMIN, CLERK, MADE, SECOND_ADMIN)))
        )

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


def _park_foreign_admins(write: Callable[[Callable[..., object]], None]) -> list[int]:
    """Выключить **чужих** действующих администраторов и вернуть их идентификаторы.

    Защита «нельзя разжаловать последнего администратора» — свойство **всей
    базы**, а не строки: любой посторонний админ делает подопытного не
    последним, и тест начинает проверять не то, что написано в его имени.
    Через `db_session` этого не обойти: приложение ходит своими соединениями,
    и откат тестовой транзакции его записей не видит.

    Дев-база при этом живёт между прогонами: у неё заводят настоящие учётки
    руками. Поэтому чужие админы не удаляются, а на время теста выключаются и
    возвращаются обратно — третий случай зависимости «зелёный по причине
    окружения» (уроки L8, L58).
    """
    parked: list[int] = []

    async def _park(session: object) -> None:
        from sqlalchemy import select as _select

        stmt = _select(User).where(
            User.group == UserGroup.ADMIN,
            User.is_active.is_(True),
            User.email.notin_((ADMIN, CLERK, MADE, SECOND_ADMIN)),
        )
        for user in (await session.execute(stmt)).scalars().all():  # type: ignore[attr-defined]
            user.is_active = False
            parked.append(user.id)

    write(_park)
    return parked


def _restore_admins(write: Callable[[Callable[..., object]], None], ids: list[int]) -> None:
    async def _restore(session: object) -> None:
        from sqlalchemy import update as _update

        if ids:
            await session.execute(  # type: ignore[attr-defined]
                _update(User).where(User.id.in_(ids)).values(is_active=True)
            )

    write(_restore)


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
    parked = _park_foreign_admins(writer)
    try:
        yield
    finally:
        _restore_admins(writer, parked)
        _cleanup(writer)


@pytest.fixture
def client(seeded: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    body = client.post("/api/auth/login", json={"email": email, "password": password}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_rights_catalog_comes_from_the_same_table(client: TestClient) -> None:
    """E7: справочник прав — из той же таблицы, что проверяют роутеры.

    Экран показывает, что человеку дала группа, а что выдали лично, и без
    справочника держал бы вторую копию таблицы прав. Копия расходится молча —
    ровно в тот день, когда таблицу правят.
    """
    from ahrefs_cases.api.deps import ALL_RIGHTS, rights_of
    from ahrefs_cases.storage import UserGroup

    body = client.get("/api/users/rights", headers=_headers(client, ADMIN)).json()

    assert set(body["rights"]) == set(ALL_RIGHTS)
    assert set(body["groups"]) == {group.value for group in UserGroup}
    assert set(body["groups"]["admin"]) == set(rights_of(UserGroup.ADMIN))
    # Слово `rights` не уезжает в `{user_id}`: иначе выдача стала бы `422`.
    assert "manage_users" in body["rights"]


def test_rights_catalog_needs_the_right(client: TestClient) -> None:
    """E8: справочник закрыт тем же правом, что и остальное управление людьми."""
    assert client.get("/api/users/rights", headers=_headers(client, CLERK)).status_code == 403


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


def _rights_of(client: TestClient, email: str) -> list[str]:
    rows = client.get("/api/users", headers=_headers(client, ADMIN)).json()
    return next(row["rights"] for row in rows if row["email"] == email)


def test_manager_cannot_take_own_management_right(client: TestClient) -> None:
    """U1: себя не лишить права управлять людьми личным «Нет».

    Так единственный инженер прода запер себя снаружи 24.09.2026: «Нет» у
    своего «добавлять пользователей» — и вернуть право стало некому, экран
    людей отвечал 403. Отказ называет, кто может это сделать.
    """
    boss = _headers(client, ADMIN)

    refused = client.patch(
        f"/api/users/{_user_id(client, ADMIN)}",
        json={"personal_rights": {"manage_users": False}},
        headers=boss,
    )

    assert refused.status_code == 409
    assert "другой управляющий" in refused.json()["detail"]
    assert "manage_users" in _rights_of(client, ADMIN)


def test_manager_cannot_leave_management_by_own_group(client: TestClient) -> None:
    """U2: и сменой своей группы тоже — правило строгое, другой управляющий есть.

    Второй администратор здесь не для красоты (урок L160): без него смену группы
    отбила бы прежняя защита «последний администратор», и тест был бы зелёным
    без новой. Поэтому утверждение — по тексту отказа, а не по коду 409.
    """
    boss = _headers(client, ADMIN)
    second = client.post("/api/users", json={"email": SECOND_ADMIN, "group": "admin"}, headers=boss)
    assert second.status_code == 201, second.text

    refused = client.patch(
        f"/api/users/{_user_id(client, ADMIN)}", json={"group": "user"}, headers=boss
    )

    assert refused.status_code == 409
    assert "другой управляющий" in refused.json()["detail"]
    assert "manage_users" in _rights_of(client, ADMIN)


def test_management_right_of_another_can_be_taken(client: TestClient) -> None:
    """U3: страж от перегиба — правило про себя, а не про само право."""
    boss = _headers(client, ADMIN)
    second = client.post("/api/users", json={"email": SECOND_ADMIN, "group": "admin"}, headers=boss)
    assert second.status_code == 201, second.text

    taken = client.patch(
        f"/api/users/{second.json()['user']['id']}",
        json={"personal_rights": {"manage_users": False}},
        headers=boss,
    )

    assert taken.status_code == 200, taken.text
    assert "manage_users" not in taken.json()["rights"]


def test_own_group_change_keeping_management_is_allowed(client: TestClient) -> None:
    """U4: страж от перегиба — запрещено терять право, а не менять свою группу.

    Второй администратор — чтобы уход из админов не отбила прежняя защита.
    """
    boss = _headers(client, ADMIN)
    second = client.post("/api/users", json={"email": SECOND_ADMIN, "group": "admin"}, headers=boss)
    assert second.status_code == 201, second.text

    moved = client.patch(
        f"/api/users/{_user_id(client, ADMIN)}", json={"group": "engineer"}, headers=boss
    )

    assert moved.status_code == 200, moved.text
    assert "manage_users" in moved.json()["rights"]


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


def _user_id(client: TestClient, email: str) -> int:
    rows = client.get("/api/users", headers=_headers(client, ADMIN)).json()
    found = next((row for row in rows if row["email"] == email), None)
    assert found is not None, f"в списке нет {email}"
    return int(found["id"])


def test_user_without_runs_is_deleted_for_real(client: TestClient) -> None:
    """Учётку, за которой ничего не числится, удаляем по-настоящему.

    Терять нечего, а почта освобождается: заведённую с опечаткой иначе
    пришлось бы обходить вечно.
    """
    boss = _headers(client, ADMIN)
    made = client.post(
        "/api/users",
        json={"email": MADE, "full_name": "Ошибка в почте", "group": "user"},
        headers=boss,
    )
    assert made.status_code == 201, made.text
    user_id = made.json()["user"]["id"]

    dropped = client.delete(f"/api/users/{user_id}", headers=boss)

    assert dropped.status_code == 204, dropped.text
    assert all(row["email"] != MADE for row in client.get("/api/users", headers=boss).json())
    # Почта свободна — тот же адрес заводится снова.
    again = client.post("/api/users", json={"email": MADE, "group": "user"}, headers=boss)
    assert again.status_code == 201, again.text


def test_user_with_runs_is_not_deleted_but_named(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """За учёткой есть прогоны — строка остаётся, а в журнале стоит «(удалён)».

    Журнал отвечает на вопрос «кто это запускал», и ответ обязан переживать
    увольнение. Поэтому из списка человек пропадает и войти не может, но
    прогоны остаются на месте и по-прежнему названы его именем.
    """
    boss = _headers(client, ADMIN)
    clerk_id = _user_id(client, CLERK)

    async def _run(session: object) -> None:
        from ahrefs_cases.storage.models.run import Run

        session.add(  # type: ignore[attr-defined]
            Run(
                started_by=clerk_id,
                status="QUEUED",
                projects_total=1,
                projects_ok=0,
                projects_failed=0,
                units_estimated=0,
                units_actual=0,
                params_snapshot={},
                error="",
            )
        )

    writer(_run)

    dropped = client.delete(f"/api/users/{clerk_id}", headers=boss)

    assert dropped.status_code == 204, dropped.text
    assert all(row["email"] != CLERK for row in client.get("/api/users", headers=boss).json())
    # Вход закрыт: удалённый не входит даже с прежним паролем.
    denied = client.post("/api/auth/login", json={"email": CLERK, "password": PASSWORD})
    assert denied.status_code == 401
    # А журнал по-прежнему называет автора — с пометкой.
    runs = client.get("/api/runs", headers=boss).json()
    mine = next((row for row in runs if row["started_by"] == clerk_id), None)
    assert mine is not None, "прогон исчез вместе с учёткой"
    assert mine["started_by_name"] == "Сотрудник"
    assert mine["started_by_deleted"] is True


def test_self_deletion_is_refused(client: TestClient) -> None:
    """Себя не удалить: удалять станет некому — та же причина, что у выключения."""
    boss = _headers(client, ADMIN)

    refused = client.delete(f"/api/users/{_user_id(client, ADMIN)}", headers=boss)

    assert refused.status_code == 409
    assert "удалять станет некому" in refused.json()["detail"]


def test_last_admin_is_not_deleted(client: TestClient) -> None:
    """Последнего администратора не удалить — управлять станет некому.

    Удаляет **третий**, а не сам админ: свою учётку он не удалит и по первому
    правилу («удалять станет некому»), а проверить нужно второе. Третьим здесь
    работает обычный сотрудник, которому лично выдали управление людьми — это и
    есть случай, ради которого личные права существуют.
    """
    boss = _headers(client, ADMIN)
    second = client.post("/api/users", json={"email": SECOND_ADMIN, "group": "admin"}, headers=boss)
    assert second.status_code == 201, second.text
    second_headers = _headers(client, SECOND_ADMIN, second.json()["password"])
    clerk_id = _user_id(client, CLERK)
    client.patch(
        f"/api/users/{clerk_id}", json={"personal_rights": {"manage_users": True}}, headers=boss
    )
    # Первого админа выключает второй: себя выключить нельзя тем же правилом.
    admin_id = _user_id(client, ADMIN)
    parked = client.patch(
        f"/api/users/{admin_id}", json={"is_active": False}, headers=second_headers
    )
    assert parked.status_code == 200, parked.text

    refused = client.delete(
        f"/api/users/{second.json()['user']['id']}", headers=_headers(client, CLERK)
    )

    assert refused.status_code == 409
    assert "последний администратор" in refused.json()["detail"]
    client.patch(f"/api/users/{admin_id}", json={"is_active": True}, headers=second_headers)


def test_deleting_needs_the_right(client: TestClient) -> None:
    """Удаление — под тем же правом, что и всё управление людьми (админ и инженер)."""
    refused = client.delete(
        f"/api/users/{_user_id(client, ADMIN)}", headers=_headers(client, CLERK)
    )

    assert refused.status_code == 403
