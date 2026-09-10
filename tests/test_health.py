"""Health-эндпоинт в трёх состояниях. Примеры приёмки A2 и A3."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ahrefs_cases.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_health_ok_with_database(client: TestClient, needs_db: None) -> None:  # noqa: ARG001
    """A2: при поднятой базе — 200, версия миграции и текущий провайдер."""
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["migration"]
    assert body["provider"] == "fixture"


def test_health_reports_unavailable_when_database_is_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A3: недоступная база даёт 503 с причиной, а не 200 и не пятисотку.

    «Процесс жив» и «сервис работает» — разные вещи. Health, отвечающий 200 при
    мёртвой базе, гарантирует, что мониторинг промолчит именно в тот момент,
    когда должен закричать.
    """
    import asyncio

    from ahrefs_cases import config, storage

    dead_dsn = "postgresql+asyncpg://cases:cases@127.0.0.1:1/cases"
    monkeypatch.setattr(config.storage, "database_url", dead_dsn)
    asyncio.run(storage.dispose_engine())
    try:
        response = client.get("/api/health")
    finally:
        asyncio.run(storage.dispose_engine())

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["reason"]
