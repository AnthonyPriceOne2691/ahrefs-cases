"""Очередь и запуск прогона по HTTP.

Примеры приёмки поставки `api-runs`: E1 (без токена), E2 (запуск), E3 (замок),
E4 (журнал), E5 (нет прогона), E6 (inline-очередь), E7 (упавшая задача),
E8 (задача кейсов), E9 (выбор очереди), E10 (простые аргументы).

Очередь в тестах — `inline`: задача выполняется в том же процессе, и это не
подмена, а рабочий режим разработки (Redis на машине может не быть).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from tests.owned_rows import delete_owned

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import RunStatus, UserGroup
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.workers import jobs, queue
from ahrefs_cases.workers.queue import InlineQueue, RedisQueue, build_queue

PASSWORD = "очень-длинный-пароль"
EMAIL = "runner@test.local"


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
        await delete_owned(session, domains=("runs.example",), emails=(EMAIL,))  # type: ignore[arg-type]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    monkeypatch.setattr(config.storage, "queue_backend", "inline")


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)

    async def _seed(session: object) -> None:
        session.add_all(  # type: ignore[attr-defined]
            [
                User(
                    email=EMAIL,
                    full_name="Оператор",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.USER,
                ),
                Project(
                    domain="runs.example",
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


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def test_start_needs_a_token(client: TestClient) -> None:
    """E1: запуск прогона тратит units — он закрыт правом `run`."""
    assert client.post("/api/runs").status_code == 401


def test_user_may_start_a_run(client: TestClient) -> None:
    """E2 и E6: право `run` есть у всех трёх групп; inline-очередь отработала."""
    response = client.post("/api/runs", headers=_headers(client))

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"] > 0
    assert body["queued_as"].startswith("inline:")


def test_second_run_is_refused_while_one_is_active(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """E3: второй прогон стоит вторую цену — отказ с номером активного."""

    headers = _headers(client)
    first = client.post("/api/runs", headers=headers).json()

    async def _hang(session: object) -> None:
        from sqlalchemy import update

        # Только **свой** прогон: `update(Run).values(...)` без условия
        # помечало «идущим» каждый прогон в базе, включая чужие, и они
        # оставались такими навсегда — следующий запуск упирался в чужой замок.
        await session.execute(  # type: ignore[attr-defined]
            update(Run).where(Run.id == first["run_id"]).values(status=RunStatus.RUNNING)
        )

    writer(_hang)

    second = client.post("/api/runs", headers=headers)

    assert second.status_code == 409
    assert str(first["run_id"]) in second.json()["detail"]


def test_journal_shows_status_and_units(client: TestClient) -> None:
    """E4: журнал считает проекты и units, а не задачи (урок L13)."""
    headers = _headers(client)
    started = client.post("/api/runs", headers=headers).json()

    rows = client.get("/api/runs", headers=headers).json()
    one = client.get(f"/api/runs/{started['run_id']}", headers=headers).json()

    assert rows[0]["id"] == started["run_id"]
    assert one["projects_total"] >= 1
    assert one["status"] in {"done", "partial", "failed", "queued", "running"}
    assert "units_actual" in one
    # Смета записана в строку прогона, а не только в резерв: журнал показывает
    # «смета → факт», и нулевая колонка врала бы у каждого прогона.
    assert one["units_estimated"] > 0


def test_refresh_run_actually_starts(client: TestClient) -> None:
    """Запуск с догрузкой доходит до задачи, а не виснет в очереди.

    Очередь пересылает аргументы **позиционно**; пока `refresh` был объявлен
    только-ключевым, вызов падал `TypeError` ещё до тела задачи. Ответ при этом
    приходил `202`, задача не начиналась, и строка оставалась `queued` навсегда —
    замок «один активный прогон» блокировал все следующие запуски.

    Поэтому проверяется не код ответа, а **состояние прогона после**: 202 здесь
    ничего не доказывает.
    """
    headers = _headers(client)

    started = client.post("/api/runs", params={"refresh": True}, headers=headers).json()

    row = client.get(f"/api/runs/{started['run_id']}", headers=headers).json()
    assert row["status"] != "queued", "задача не начиналась: прогон завис в очереди"
    assert row["units_estimated"] >= 0


def test_missing_run_is_404(client: TestClient) -> None:
    """E5: несуществующий прогон — 404, а не пустая карточка."""
    assert client.get("/api/runs/999999", headers=_headers(client)).status_code == 404


def test_failed_job_marks_the_run(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """E7: наблюдателя снаружи нет, отметить падение обязана сама задача (L24)."""
    headers = _headers(client)
    run_id = client.post("/api/runs", headers=headers).json()["run_id"]

    def _boom(_run_id: int) -> None:
        message = "нарочно сломано"
        raise RuntimeError(message)

    with pytest.raises(RuntimeError):
        asyncio.run(jobs._run_guarded(run_id, _explode()))

    row = client.get(f"/api/runs/{run_id}", headers=headers).json()
    assert row["status"] == "failed"
    assert "нарочно сломано" in row["error"]


async def _explode() -> str:
    message = "нарочно сломано"
    raise RuntimeError(message)


def test_cases_job_uses_the_same_queue(client: TestClient) -> None:
    """E8: сборка пачки ставится тем же способом и тем же замком."""
    response = client.post("/api/runs/cases", headers=_headers(client))

    assert response.status_code == 202
    assert response.json()["queued_as"].startswith("inline:")


def test_queue_is_chosen_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """E9: одно место решает «сразу или воркером» (урок L53)."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.storage, "queue_backend", "inline")
    assert isinstance(build_queue(), InlineQueue)

    monkeypatch.setattr(config.storage, "queue_backend", "redis")
    monkeypatch.setattr(queue, "RedisQueue", lambda: "redis-очередь")
    assert build_queue() == "redis-очередь"


def test_job_arguments_are_plain_values() -> None:
    """E10: задача уезжает в другой процесс — сессия и объекты туда не доедут."""
    import inspect

    for job in (jobs.collect_job, jobs.cases_job):
        for name, parameter in inspect.signature(job).parameters.items():
            assert parameter.annotation in {"int", "bool"}, f"{job.__name__}: {name}"
    assert RedisQueue is not None  # реализация существует и импортируется без Redis
