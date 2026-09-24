"""Экран расхода: «потрачено» и стоимость на сто доменов — только живые units.

Примеры приёмки поставки `usage-counts-live-units-only`: R1 (fixture-прогон с
тратой не входит ни в «потрачено», ни в стоимость на сто доменов), R2 (живой
входит ровно своей суммой, его домен — в знаменатель).

База общая и живёт между прогонами: на стенде лежат и живые, и
fixture-прогоны, а приложение ходит своими соединениями, так что обнулить её
откатом транзакции нельзя. Поэтому тест сверяет не абсолютные числа, а
**приращение** от своих строк — метаморфное отношение: добавили fixture-прогон —
«потрачено» не сдвинулось; добавили живой на S units — сдвинулось ровно на S.
Точные числа на пустой базе — в `test_budget_spend.py`.

Пишет только свои строки (свой пользователь, свои домены) и убирает их по
владению (`tests/owned_rows.py`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.owned_rows import delete_owned

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage._enums import LedgerKind, RunItemOutcome, RunStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run, RunItem
from ahrefs_cases.storage.models.units_ledger import UnitsLedger
from ahrefs_cases.storage.models.user import User

PASSWORD = "очень-длинный-пароль"
EMAIL = "usage-reader@test.local"
FIXTURE_DOMAIN = "usage-fixture.example"
LIVE_DOMAIN = "usage-live.example"
DOMAINS = (FIXTURE_DOMAIN, LIVE_DOMAIN)

Write = Callable[[Callable[[AsyncSession], Any]], None]


@pytest.fixture(scope="module")
def writer() -> Iterator[Write]:
    """Один цикл и один движок на модуль — для записи мимо приложения.

    Тот же приём, что в `test_api_read.py`: движок на каждый вызов оставлял
    закрытые соединения сборщику мусора, и `ResourceWarning` всплывал в
    случайном тесте (L51).
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from ahrefs_cases import config

    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Callable[[AsyncSession], Any]) -> None:
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


def _cleanup(write: Write) -> None:
    async def _delete(session: AsyncSession) -> None:
        await delete_owned(session, domains=DOMAINS, emails=(EMAIL,))

    write(_delete)


@pytest.fixture
def client(migrated_db: None, writer: Write) -> Iterator[TestClient]:
    """Читатель расхода — своя учётка: автор прогонов теста берётся из базы (L58)."""
    _cleanup(writer)

    async def _reader(session: AsyncSession) -> None:
        session.add(
            User(
                email=EMAIL,
                full_name="Читатель расхода",
                password_hash=security.hash_password(PASSWORD),
                group=UserGroup.USER,
            )
        )

    writer(_reader)
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        _cleanup(writer)


def _usage(client: TestClient) -> dict[str, Any]:
    """Ответ экрана расхода. Отказ — исключение, а не данные для сравнения."""
    login = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    login.raise_for_status()
    token = login.json()["access_token"]
    response = client.get("/api/usage", headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body


def _add_run(write: Write, *, provider: str, domain: str, units: int) -> None:
    """Закрытый прогон своего пользователя: один проект, одна строка расхода."""

    async def _seed(session: AsyncSession) -> None:
        author = (await session.execute(select(User.id).where(User.email == EMAIL))).scalar_one()
        project = Project(
            domain=domain,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 1),
            niche="fintech",
            geo="US",
            service_type="seo",
            client="Acme",
            owner="i.petrov",
            publishable=False,
            notes="",
        )
        session.add(project)
        await session.flush()
        run = Run(
            started_by=author,
            status=RunStatus.DONE,
            projects_total=1,
            projects_ok=1,
            units_estimated=units,
            units_actual=units,
            params_snapshot={"provider": provider},
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                RunItem(
                    run_id=run.id,
                    project_id=project.id,
                    raw_domain=domain,
                    outcome=RunItemOutcome.OK,
                    units_actual=units,
                ),
                UnitsLedger(
                    run_id=run.id,
                    kind=LedgerKind.SPENT,
                    endpoint="metrics-history",
                    target=domain,
                    units_estimated=units,
                    units_actual=units,
                    rows=1,
                ),
            ]
        )

    write(_seed)


def test_fixture_run_is_not_spent(client: TestClient, writer: Write) -> None:
    """R1: fixture-прогон с тратой не входит ни в «потрачено», ни в стоимость на сто.

    Fixture-режим считает условные units той же формулой, что живой API. До
    правки экран складывал их с настоящими: «потрачено» вырастало на 700, а
    стоимость на сто доменов менялась от проекта, в Ahrefs не ходившего.
    """
    before = _usage(client)

    _add_run(writer, provider="fixture", domain=FIXTURE_DOMAIN, units=700)
    after = _usage(client)

    assert after["spent"] == before["spent"]
    assert after["per_hundred_domains"] == before["per_hundred_domains"]
    assert after["live_domains"] == before["live_domains"]
    # Условные units не пропадают, а названы отдельно — ровно своей суммой.
    assert after["conditional"] - before["conditional"] == 700


def test_live_run_is_spent_exactly(client: TestClient, writer: Write) -> None:
    """R2: живой прогон входит в «потрачено» ровно своей суммой, его домен — в знаменатель."""
    before = _usage(client)

    _add_run(writer, provider="live", domain=LIVE_DOMAIN, units=300)
    after = _usage(client)

    assert after["spent"] - before["spent"] == 300
    assert after["live_domains"] - before["live_domains"] == 1
    assert after["conditional"] == before["conditional"]
    # Стоимость на сто сходится со своими слагаемыми — теми, что показаны рядом.
    assert after["per_hundred_domains"] == round(after["spent"] / after["live_domains"] * 100)
