"""Скриншоты через API: загрузка, список, картинка, удаление и права.

Примеры приёмки поставки `screenshots-api`: M48 (специалист загружает скрин,
карточка его видит, картинка отдаётся с честными заголовками), M49 (не картинка,
слишком большой и пустой — отказ словами), M50 (тот же скрин дважды и предел на
проект), M51 (право `edit_briefs`: без него смотреть можно, загружать и убирать —
нет), M52 (удаление уносит строку и файл), M53 (удаление проекта уносит его скрины).

Строки свои — проект `shots.screens.example` и люди `*@screens.test.local`; каталог
скриншотов подменён временным: настоящие файлы стенда тест не видит.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.owned_rows import delete_owned

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.api.routers import screenshots as screenshots_router
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage import models as db

PASSWORD = "очень-длинный-пароль"
DOMAIN = "shots.screens.example"
CLERK, REVOKED, ENGINEER = (
    "clerk@screens.test.local",
    "revoked@screens.test.local",
    "engineer@screens.test.local",
)
PEOPLE: dict[str, tuple[UserGroup, dict[str, bool]]] = {
    CLERK: (UserGroup.USER, {}),
    REVOKED: (UserGroup.USER, {"edit_briefs": False}),
    ENGINEER: (UserGroup.ENGINEER, {}),
}

Ask = Callable[[AsyncSession], Awaitable[Any]]


def _png(width: int = 320, color: str = "white") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, 200), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Ask], Any]]:
    """Свой цикл и движок на модуль — запись мимо приложения, его движок закрывает `lifespan`."""
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
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config.export, "screenshots_dir", tmp_path / "screens")
    monkeypatch.setattr(config.export, "output_dir", tmp_path / "out")
    return tmp_path / "screens"


@pytest.fixture
def client(project_id: int, root: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, email: str = CLERK) -> dict[str, str]:
    body = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _upload(client: TestClient, project_id: int, raw: bytes, email: str = CLERK) -> Any:
    return client.post(
        f"/api/projects/{project_id}/screenshots",
        params={"kind": "ahrefs", "caption": "Обзор · Германия (DE)"},
        content=raw,
        headers=_headers(client, email),
    )


def test_specialist_uploads_and_the_card_sees_it(
    client: TestClient, project_id: int, root: Path
) -> None:
    """M48: 201 и строка в списке; картинка — PNG с честными заголовками; файл в каталоге проекта."""
    uploaded = _upload(client, project_id, _png())

    assert uploaded.status_code == 201
    shot = uploaded.json()
    assert (shot["kind"], shot["caption"], shot["width"]) == (
        "ahrefs",
        "Обзор · Германия (DE)",
        320,
    )
    listed = client.get(f"/api/projects/{project_id}/screenshots", headers=_headers(client))
    assert [row["id"] for row in listed.json()] == [shot["id"]]
    image = client.get(f"/api/screenshots/{shot['id']}/image", headers=_headers(client))
    assert image.headers["content-type"] == "image/png"
    assert image.headers["x-content-type-options"] == "nosniff"
    assert Image.open(BytesIO(image.content)).format == "PNG"
    assert len(list((root / str(project_id)).iterdir())) == 1


def test_wrong_body_is_refused_in_words(
    client: TestClient, project_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M49: не картинка — 415, пусто — 400, больше предела — 413; всё словами."""
    not_image = _upload(client, project_id, b"%PDF-1.7 not an image")
    empty = _upload(client, project_id, b"")
    monkeypatch.setattr(screenshots_router, "MAX_SCREEN_BYTES", 100)
    too_big = _upload(client, project_id, _png())

    assert not_image.status_code == 415
    assert "PNG, JPEG или WebP" in not_image.json()["detail"]
    assert empty.status_code == 400
    assert too_big.status_code == 413
    assert "2,5 МБ" in too_big.json()["detail"]


def test_same_image_twice_and_the_cap(
    client: TestClient, project_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M50: та же картинка дважды — 409; предел на проект — 409 со словами, что делать."""
    assert _upload(client, project_id, _png()).status_code == 201
    twin = _upload(client, project_id, _png())
    monkeypatch.setattr(screenshots_router, "MAX_PER_PROJECT", 1)
    over = _upload(client, project_id, _png(color="black"))

    assert twin.status_code == 409
    assert "уже есть" in twin.json()["detail"]
    assert over.status_code == 409
    assert "уберите лишние" in over.json()["detail"]


def test_without_the_right_one_may_look_but_not_change(client: TestClient, project_id: int) -> None:
    """M51: личное «Нет» на `edit_briefs` — смотреть можно, загружать и убирать — нет."""
    shot = _upload(client, project_id, _png()).json()
    viewer = _headers(client, REVOKED)

    assert _upload(client, project_id, _png(color="black"), email=REVOKED).status_code == 403
    assert client.delete(f"/api/screenshots/{shot['id']}", headers=viewer).status_code == 403
    listed = client.get(f"/api/projects/{project_id}/screenshots", headers=viewer)
    assert listed.status_code == 200
    image = client.get(f"/api/screenshots/{shot['id']}/image", headers=viewer)
    assert image.status_code == 200


def test_delete_takes_the_row_and_the_file(client: TestClient, project_id: int, root: Path) -> None:
    """M52: строка и файл уходят вместе; картинка после этого — 404 словами."""
    shot = _upload(client, project_id, _png()).json()

    removed = client.delete(f"/api/screenshots/{shot['id']}", headers=_headers(client))

    assert removed.status_code == 200
    listed = client.get(f"/api/projects/{project_id}/screenshots", headers=_headers(client))
    assert listed.json() == []
    assert not list((root / str(project_id)).iterdir())
    gone = client.get(f"/api/screenshots/{shot['id']}/image", headers=_headers(client))
    assert gone.status_code == 404


def test_project_deletion_takes_its_screenshots(
    client: TestClient, project_id: int, root: Path
) -> None:
    """M53: предпросмотр удаления называет скрины; удаление уносит строки и каталог проекта."""
    _upload(client, project_id, _png())
    engineer = _headers(client, ENGINEER)

    preview = client.get(f"/api/projects/{project_id}/deletion", headers=engineer)
    deleted = client.delete(f"/api/projects/{project_id}", headers=engineer)

    assert preview.json()["screenshots"] == 1
    assert deleted.status_code == 200
    assert not (root / str(project_id)).exists()
