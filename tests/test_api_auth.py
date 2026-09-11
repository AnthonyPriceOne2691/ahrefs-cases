"""Вход в сервис: пароли, токены и права на роутере.

Примеры приёмки поставки `api-auth`: E1 (вход), E2 (одинаковый отказ), E3
(выключенный), E4 (без токена), E5 (испорченный токен), E6 и E7 (права),
E8 (пустой секрет), E9 (хеш пароля), E10 (правило прав в одном месте).

Секрет подписи задаётся фикстурой, а не берётся из `.env` разработчика: тест,
стоящий на чужой машине, зелёный только на ней (урок L21).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from ahrefs_cases.api import security
from ahrefs_cases.api.deps import require_right, rights_of
from ahrefs_cases.api.main import app, lifespan
from ahrefs_cases.api.routers import auth_router
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.user import User

PASSWORD = "очень-длинный-пароль"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Свой секрет на тест: подпись не должна зависеть от окружения машины."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


@pytest.fixture
def client(migrated_db: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def guarded_client(client: TestClient) -> Iterator[TestClient]:
    """Приложение с одним защищённым роутером: право проверяется на нём.

    Собственное приложение, а не чужой рабочий роутер: поставка проверяет
    механику прав, и вешать её проверку на первый попавшийся эндпоинт значит
    связать тест прав с чужой логикой.
    """
    # `lifespan` наш, а не по умолчанию: на выходе он закрывает движок базы.
    # Приложение без него оставляет открытыми соединения, и они всплывают
    # `ResourceWarning`ом в чужом тесте — а `filterwarnings = ["error"]`
    # превращает это в падение там, где ничего не ломали.
    guarded = FastAPI(lifespan=lifespan)
    router = APIRouter()

    @router.get("/api/thresholds-stub", dependencies=[Depends(require_right("edit_thresholds"))])
    async def _stub() -> dict[str, str]:
        return {"ok": "да"}

    guarded.include_router(router)
    guarded.include_router(auth_router)
    with TestClient(guarded, raise_server_exceptions=False) as test_client:
        yield test_client


def _write(action: object) -> None:
    """Выполнить запись **своим** движком и закрыть его.

    Кэшированный движок проекта привязан к циклу, в котором создан, а каждый
    `asyncio.run` — новый цикл: повторный вызов через тот же движок падает
    «attached to a different loop». Тот же приём, что у фикстуры `db_session`
    в conftest, и по той же причине.
    """

    async def _main() -> None:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

        from ahrefs_cases import config

        engine = create_async_engine(config.storage.database_url)
        try:
            async with AsyncSession(engine) as session:
                await action(session)  # type: ignore[operator]
                await session.commit()
        finally:
            await engine.dispose()
            for _ in range(3):
                await asyncio.sleep(0)

    asyncio.run(_main())


def _cleanup(email: str) -> None:
    async def _delete(session: object) -> None:
        from sqlalchemy import delete

        await session.execute(delete(User).where(User.email == email))  # type: ignore[attr-defined]

    _write(_delete)


def _create_user(email: str, group: UserGroup, *, active: bool = True) -> None:
    """Пользователь пишется своей сессией: TestClient ходит в ту же базу.

    Чистка идёт и **перед** записью: сессия здесь коммитит, то есть живёт вне
    транзакции теста, и упавший прогон оставляет строку следующему (урок L8).
    """
    _cleanup(email)

    async def _add(session: object) -> None:
        session.add(  # type: ignore[attr-defined]
            User(
                email=email,
                full_name="Тест",
                password_hash=security.hash_password(PASSWORD),
                group=group,
                is_active=active,
            )
        )

    _write(_add)


@pytest.fixture
def engineer() -> Iterator[str]:
    email = "engineer@test.local"
    _create_user(email, UserGroup.ENGINEER)
    yield email
    _cleanup(email)


@pytest.fixture
def plain_user() -> Iterator[str]:
    email = "user@test.local"
    _create_user(email, UserGroup.USER)
    yield email
    _cleanup(email)


def _login(client: TestClient, email: str, password: str = PASSWORD) -> object:
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_returns_token_group_and_rights(client: TestClient, plain_user: str) -> None:
    """E1: интерфейс рисует навигацию по правам, поэтому они приходят сразу."""
    response = _login(client, plain_user)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["group"] == "user"
    assert body["rights"] == sorted(rights_of(UserGroup.USER))
    assert body["access_token"]


def test_wrong_password_and_unknown_email_answer_the_same(
    client: TestClient, plain_user: str
) -> None:
    """E2: разные ответы превращают форму входа в перечислитель адресов."""
    wrong = _login(client, plain_user, "не тот пароль")
    unknown = _login(client, "нет-такого@test.local")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_disabled_user_cannot_log_in(client: TestClient) -> None:
    """E3: выключить — значит закрыть вход, а не спрятать из списка."""
    email = "off@test.local"
    _create_user(email, UserGroup.ADMIN, active=False)
    try:
        assert _login(client, email).status_code == 401
    finally:
        _cleanup(email)


def test_protected_route_needs_a_token(guarded_client: TestClient) -> None:
    """E4: без заголовка — 401, а не 403: неизвестно даже, кто спрашивает."""
    assert guarded_client.get("/api/thresholds-stub").status_code == 401


_BROKEN_JWT = "eyJhbGciOiJIUzI1NiJ9.e30.bad"  # pragma: allowlist secret — заведомо битый токен


@pytest.mark.parametrize("token", ["garbage", "a.b.c", _BROKEN_JWT])
def test_broken_token_is_rejected(guarded_client: TestClient, token: str) -> None:
    """E5: причина отказа остаётся в логе, наружу уходит один ответ.

    Значения — латиницей нарочно: заголовки HTTP кодируются latin-1, и токен с
    кириллицей не дойдёт до сервиса вовсе — его отвергнет клиент.
    """
    response = guarded_client.get(
        "/api/thresholds-stub", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_expired_token_is_rejected(guarded_client: TestClient, plain_user: str) -> None:
    """E5: просроченный токен неотличим снаружи от испорченного — и это верно."""
    from ahrefs_cases import config

    config.auth.jwt_ttl_hours = 1
    claims = security.TokenClaims(user_id=1, email=plain_user, group=UserGroup.USER)
    token = security.issue_token(claims)

    import jwt as pyjwt

    expired = pyjwt.encode(
        {**pyjwt.decode(token, config.auth.jwt_secret, algorithms=["HS256"]), "exp": 1},
        config.auth.jwt_secret,
        algorithm="HS256",
    )
    response = guarded_client.get(
        "/api/thresholds-stub", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401


def test_user_may_not_edit_thresholds_but_engineer_may(
    guarded_client: TestClient, plain_user: str, engineer: str
) -> None:
    """E6 и E7: различие групп сейчас ровно одно — правка порогов."""
    user_token = _login(guarded_client, plain_user).json()["access_token"]
    engineer_token = _login(guarded_client, engineer).json()["access_token"]

    denied = guarded_client.get(
        "/api/thresholds-stub", headers={"Authorization": f"Bearer {user_token}"}
    )
    allowed = guarded_client.get(
        "/api/thresholds-stub", headers={"Authorization": f"Bearer {engineer_token}"}
    )

    assert denied.status_code == 403
    assert "edit_thresholds" in denied.json()["detail"]
    assert allowed.status_code == 200


def test_empty_secret_issues_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """E8: подпись пустым секретом подделывается — значит подписи нет."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "")
    with pytest.raises(security.SecretMissingError):
        security.issue_token(security.TokenClaims(user_id=1, email="a@b.c", group=UserGroup.USER))


def test_password_is_stored_hashed() -> None:
    """E9: исходный пароль не восстановим, а испорченный хеш — «не подошёл»."""
    hashed = security.hash_password(PASSWORD)

    assert PASSWORD not in hashed
    assert security.verify_password(PASSWORD, hashed)
    assert not security.verify_password("другой", hashed)
    assert not security.verify_password(PASSWORD, "обрезанный-хеш")


def test_rights_live_in_one_table() -> None:
    """E10: у модели пользователя копии правила больше нет."""
    assert not hasattr(User, "can_edit_thresholds")
    assert "edit_thresholds" in rights_of(UserGroup.ADMIN)
    assert "edit_thresholds" not in rights_of(UserGroup.USER)
    assert "change_technical_settings" in rights_of(UserGroup.ENGINEER)
    assert "change_technical_settings" not in rights_of(UserGroup.ADMIN)
