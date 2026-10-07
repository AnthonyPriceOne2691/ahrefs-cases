"""Бриф проекта через API: каталог полей, правка, NDA и права.

Примеры приёмки поставки `brief-fields-api`: M18 (каталог виден читающим), M19
(специалист заполняет бриф, карточка его отдаёт), M20 (правка частичная, пустое
очищает), M21 (негодное поле — отказ словами, не пишется ничего), M22 (NDA —
это `publishable` наоборот), M23 (право `edit_briefs`: у всех групп, лично
отбирается).

Строки свои — проект `card.brief.example` и люди `*@brief.test.local`: дев-база
общая, тест убирает только созданное им (L80, L148).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.owned_rows import delete_owned

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage import models as db

PASSWORD = "очень-длинный-пароль"
DOMAIN = "card.brief.example"
CLERK, REVOKED = "clerk@brief.test.local", "revoked@brief.test.local"
PEOPLE: dict[str, tuple[UserGroup, dict[str, bool]]] = {
    CLERK: (UserGroup.USER, {}),
    REVOKED: (UserGroup.ENGINEER, {"edit_briefs": False}),
}
DRIVE = "https://drive.google.com/drive/folders/brief-test"

Ask = Callable[[AsyncSession], Awaitable[Any]]


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Ask], Any]]:
    """Свой цикл и движок на модуль — запись мимо приложения (уроки L51, L54)."""
    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Ask) -> Any:
        async def _apply() -> Any:
            async with AsyncSession(engine) as session:
                found = await action(session)
                await session.commit()
                return found

        return loop.run_until_complete(_apply())

    try:
        yield run
    finally:
        loop.run_until_complete(engine.dispose())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


async def _cleanup(session: AsyncSession) -> None:
    await delete_owned(session, domains=(DOMAIN,), emails=tuple(PEOPLE))


async def _seed(session: AsyncSession) -> int:
    hashed = security.hash_password(PASSWORD)
    session.add_all(
        db.User(email=email, password_hash=hashed, group=group, permissions=personal)
        for email, (group, personal) in PEOPLE.items()
    )
    project = db.Project(
        domain=DOMAIN,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 1),
        niche="travel",
        geo="DE",
        service_type="seo",
        client="Acme",
        owner="i.p",
        publishable=True,
    )
    session.add(project)
    await session.flush()
    return project.id


@pytest.fixture
def project_id(migrated_db: None, writer: Callable[[Ask], Any]) -> Iterator[int]:
    writer(_cleanup)
    yield writer(_seed)
    writer(_cleanup)


@pytest.fixture
def client(project_id: int, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, email: str = CLERK) -> dict[str, str]:
    body = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _patch(client: TestClient, project_id: int, body: dict[str, Any], email: str = CLERK) -> Any:
    return client.patch(
        f"/api/projects/{project_id}/brief", json=body, headers=_headers(client, email)
    )


def _card(client: TestClient, project_id: int) -> dict[str, Any]:
    response = client.get(f"/api/projects/{project_id}", headers=_headers(client))
    assert response.status_code == 200
    return dict(response.json())


def test_catalog_is_open_to_readers(client: TestClient) -> None:
    """M18: каталог полей читает любая группа; без входа — 401, как всё остальное."""
    response = client.get("/api/brief-fields", headers=_headers(client))

    assert response.status_code == 200
    catalog = response.json()
    assert catalog["sections"][0] == "Инфо о сотруднике"
    by_key = {field["key"]: field for field in catalog["fields"]}
    assert "Очень высокая" in [choice["label"] for choice in by_key["complexity"]["choices"]]
    assert by_key["folder_url"]["column"] == "folder_url"
    assert client.get("/api/brief-fields").status_code == 401


def test_specialist_fills_the_brief(client: TestClient, project_id: int) -> None:
    """M19: группа user пишет бриф; пункт списка словами хранится ключом; карточка его отдаёт."""
    fields = {"client_request": "рост заявок", "site_type": "Маркетплейс", "folder_url": DRIVE}
    response = _patch(client, project_id, {"fields": fields})

    assert response.status_code == 200
    stored = {"client_request": "рост заявок", "site_type": "marketplace", "folder_url": DRIVE}
    assert response.json()["fields"] == stored
    assert _card(client, project_id)["brief"] == stored


def test_patch_is_partial_and_empty_clears(client: TestClient, project_id: int) -> None:
    """M20: не названное поле не трогается, пустая строка очищает названное."""
    _patch(client, project_id, {"fields": {"client_request": "рост", "goals": "топ-10"}})

    response = _patch(client, project_id, {"fields": {"client_request": ""}})

    assert response.status_code == 200
    assert _card(client, project_id)["brief"] == {"goals": "топ-10"}


def test_bad_field_saves_nothing(client: TestClient, project_id: int) -> None:
    """M21: отказ называет каждое негодное поле подписью, а годные того же запроса не пишутся."""
    fields = {"goals": "рост", "complexity": "адская", "folder_url": "http://x", "nonsense": "1"}
    response = _patch(client, project_id, {"fields": fields})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Сложность проекта" in detail
    assert "Папка проекта на Google Drive" in detail
    assert "nonsense" in detail
    assert _card(client, project_id)["brief"] == {}


def test_nda_is_publishable_inverted(client: TestClient, project_id: int) -> None:
    """M22: флажок NDA пишет `publishable` наоборот — второго поля нет."""
    closed = _patch(client, project_id, {"nda": True})

    assert closed.json()["nda"] is True
    assert _card(client, project_id)["project"]["publishable"] is False

    _patch(client, project_id, {"nda": False})
    assert _card(client, project_id)["project"]["publishable"] is True


def test_edit_right_is_everyones_and_personal(client: TestClient, project_id: int) -> None:
    """M23: право у группы user есть; личное «Нет» его отбирает; чужой проект — 404."""
    rights = client.post("/api/auth/login", json={"email": CLERK, "password": PASSWORD})

    assert "edit_briefs" in rights.json()["rights"]
    assert _patch(client, project_id, {"nda": True}, email=REVOKED).status_code == 403
    assert _patch(client, 10**9, {"nda": True}).status_code == 404
