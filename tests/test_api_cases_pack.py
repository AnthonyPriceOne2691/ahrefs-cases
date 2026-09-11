"""Выдача пачки кейсов по HTTP.

Примеры приёмки поставки `web-cases`: E9 (пачка есть), E10 (пачки нет — это
ответ, а не ошибка), E11 (скачивание без архива — `404`), E12 (скачивание
отдаёт тот самый файл).

Каталог выгрузки подменяется на временный: тест не должен ни видеть настоящую
пачку дев-стенда, ни оставлять свою рядом с ней.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from tests.owned_rows import delete_owned

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.user import User

PASSWORD = "очень-длинный-пароль"
EMAIL = "packer@test.local"


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
    """Своя сессия для записи мимо приложения — один цикл на модуль (урок L51)."""
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


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


@pytest.fixture
def out_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Каталог выгрузки на время теста. Настоящий остаётся нетронутым."""
    from ahrefs_cases import config

    target = tmp_path / "out"
    target.mkdir()
    monkeypatch.setattr(config.export, "output_dir", target)
    return target


@pytest.fixture
def reader(
    migrated_db: None,
    writer: Callable[[Callable[..., object]], None],
) -> Iterator[None]:
    """Человек с правом `read`: пачка закрыта тем же правом, что и библиотека."""

    async def _cleanup(session: object) -> None:
        await delete_owned(session, emails=(EMAIL,))  # type: ignore[arg-type]

    async def _seed(session: object) -> None:
        session.add(  # type: ignore[attr-defined]
            User(
                email=EMAIL,
                full_name="Забирающий пачку",
                password_hash=security.hash_password(PASSWORD),
                group=UserGroup.USER,
            )
        )

    writer(_cleanup)
    writer(_seed)
    yield
    writer(_cleanup)


@pytest.fixture
def client(reader: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _token(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_pack_needs_a_token(client: TestClient, out_dir: Path) -> None:
    """Выдача результата закрыта так же, как всё остальное чтение."""
    assert client.get("/api/cases/pack").status_code == 401


def test_missing_pack_is_an_answer(client: TestClient, out_dir: Path) -> None:
    """E10: пачки нет — код 200 и слова почему.

    `404` здесь означал бы «выдача сломана», а сломано ничего: кейсы просто
    ещё не собирали, и человеку нужен следующий шаг, а не код ошибки.
    """
    body = client.get("/api/cases/pack", headers=_token(client)).json()

    assert body["exists"] is False
    assert body["filename"] is None
    assert "собер" in body["note"].lower()


def test_pack_reports_the_newest_archive(client: TestClient, out_dir: Path) -> None:
    """E9: имя, размер и время сборки — свежего архива, а не первого попавшегося."""
    old = out_dir / "кейсы-2026-09-01.zip"
    old.write_bytes("PK\x03\x04старая".encode())
    fresh = out_dir / "кейсы-2026-09-11.zip"
    fresh.write_bytes("PK\x03\x04свежая пачка".encode())
    # Время файла, а не имя: сборка одного дня переписывает архив того же имени,
    # и «свежий по алфавиту» разошёлся бы с «собранным последним».
    older, newer = 1_757_000_000, 1_757_600_000
    os.utime(old, (older, older))
    os.utime(fresh, (newer, newer))

    body = client.get("/api/cases/pack", headers=_token(client)).json()

    assert body["exists"] is True
    assert body["filename"] == "кейсы-2026-09-11.zip"
    assert body["size_bytes"] == fresh.stat().st_size
    assert body["built_at"] == datetime.fromtimestamp(newer, tz=UTC).isoformat().replace(
        "+00:00", "Z"
    )


def test_pack_download_without_archive_is_404(client: TestClient, out_dir: Path) -> None:
    """E11: пустой файл вместо архива читался бы как испорченная пачка."""
    response = client.get("/api/cases/pack/download", headers=_token(client))

    assert response.status_code == 404
    assert "прогоном" in response.json()["detail"]


def test_pack_download_returns_the_file(client: TestClient, out_dir: Path) -> None:
    """E12: отдаётся тот самый ZIP и под тем же именем, что лежит на диске."""
    archive = out_dir / "кейсы-2026-09-11.zip"
    archive.write_bytes("PK\x03\x04пачка кейсов".encode())

    response = client.get("/api/cases/pack/download", headers=_token(client))

    assert response.status_code == 200
    assert response.content == archive.read_bytes()
    # Имя кириллическое, и в заголовке оно уезжает процентами (RFC 5987).
    # Спрашиваем про имя, которое увидит человек, а не про его кодировку.
    assert "кейсы-2026-09-11.zip" in unquote(response.headers["content-disposition"])


def test_pack_word_does_not_become_a_case_id(client: TestClient, out_dir: Path) -> None:
    """Маршрут `pack` объявлен выше `/{case_id}`: иначе выдача стала бы `422`.

    Ловушка уже срабатывала на смете прогона, и стоит она дёшево ровно до тех
    пор, пока про неё помнит тест, а не человек.
    """
    assert client.get("/api/cases/pack", headers=_token(client)).status_code == 200
