"""Проверка здоровья воркера для Docker: жив ли он с точки зрения очереди.

Смотрится не процесс, а то, что видит очередь: воркер этого контейнера
зарегистрирован в Redis, и его отметка о жизни свежая. Зависший `await`
процесс не убивает, но отметку обновлять перестаёт — это главное, что ловится.

Docker (не swarm) по `unhealthy` контейнер не перезапускает, только показывает
в `docker compose ps`. Самоубийства по зависанию нет нарочно: воркер, убитый
посреди платного прогона, при повторе заплатил бы за тот же запрос дважды.
"""

from __future__ import annotations

import logging
import socket
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol

from redis import Redis
from rq import Worker

from ahrefs_cases import config

logger = logging.getLogger(__name__)

SLACK = timedelta(seconds=60)
"""Запас сверх срока жизни ключа: RQ обновляет отметку не секунда в секунду."""


class Registered(Protocol):
    """То, что проверка читает у воркера из Redis. Протоколом — ради теста без Redis."""

    hostname: str | None
    last_heartbeat: datetime | None
    worker_ttl: int


def problem(workers: Sequence[Registered], host: str, now: datetime) -> str | None:
    """Почему воркер нездоров — или `None`, если здоров."""
    mine = [worker for worker in workers if worker.hostname == host]
    if not mine:
        return f"воркер хоста {host} не зарегистрирован в очереди"
    beat = mine[0].last_heartbeat
    if beat is None:
        return f"у воркера хоста {host} нет отметки о жизни"
    if beat.tzinfo is None:
        beat = beat.replace(tzinfo=UTC)
    age = now - beat
    limit = timedelta(seconds=mine[0].worker_ttl) + SLACK
    if age > limit:
        return (
            f"последняя отметка воркера {int(age.total_seconds())} с назад "
            f"при пределе {int(limit.total_seconds())} с — похоже на зависание"
        )
    return None


def main() -> int:
    host = socket.gethostname()
    try:
        workers = Worker.all(connection=Redis.from_url(config.storage.redis_url))
    except Exception as exc:
        # Причина уходит и в вывод проверки (`docker inspect`), и в журнал:
        # вывод проверки хранится коротко, журнал — сколько живёт контейнер.
        logger.warning("worker_health_queue_unreachable", extra={"host": host, "error": str(exc)})
        print(f"очередь недоступна: {exc}", file=sys.stderr)
        return 1
    reason = problem(workers, host, datetime.now(UTC))
    if reason is not None:
        logger.warning("worker_unhealthy", extra={"host": host, "reason": reason})
        print(reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
