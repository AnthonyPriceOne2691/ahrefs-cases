"""Проверка здоровья воркера: решение без Redis.

Сама проверка стоит в компоузе (`python -m ahrefs_cases.workers.health`); здесь
— правило, по которому она отвечает. Три исхода, и у каждого своя причина
словами: `docker inspect` покажет её человеку, а «unhealthy» без причины
отправил бы гадать.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ahrefs_cases.workers.health import problem

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


@dataclass
class FakeWorker:
    hostname: str | None
    last_heartbeat: datetime | None
    worker_ttl: int = 420


def test_fresh_heartbeat_is_healthy() -> None:
    assert problem([FakeWorker("web-1", NOW - timedelta(seconds=30))], "web-1", NOW) is None


def test_worker_of_another_container_does_not_count() -> None:
    """Воркер соседнего контейнера жив — это не значит, что жив наш."""
    reason = problem([FakeWorker("other", NOW)], "mine", NOW)
    assert reason is not None
    assert "mine" in reason


def test_stale_heartbeat_names_its_age() -> None:
    """Зависший воркер: отметка старше срока жизни ключа с запасом."""
    reason = problem([FakeWorker("mine", NOW - timedelta(seconds=600))], "mine", NOW)
    assert reason is not None
    assert "600" in reason


def test_heartbeat_within_ttl_and_slack_is_not_a_hang() -> None:
    """RQ обновляет отметку не секунда в секунду: 470 с при сроке 420 — ещё норма."""
    assert problem([FakeWorker("mine", NOW - timedelta(seconds=470))], "mine", NOW) is None
