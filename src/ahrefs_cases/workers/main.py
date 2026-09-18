"""Точка входа RQ-воркера.

Задач пока нет — они приходят в Ф2 (прогон сбора) и Ф4 (сборка пачки кейсов).
Воркер отдельным процессом с первого дня по причине из
`docs/IMPLEMENTATION_V3.md` §3: убитый прогон стоит units, а не только времени.
"""

from __future__ import annotations

import logging

from redis import Redis
from rq import Queue, Worker

from ahrefs_cases import config
from ahrefs_cases.logs import setup_logging

logger = logging.getLogger(__name__)


def build_worker() -> Worker:
    connection = Redis.from_url(config.storage.redis_url)
    queue = Queue(config.storage.queue_name, connection=connection)
    return Worker([queue], connection=connection)


def main() -> None:
    setup_logging()
    logger.info(
        "worker: очередь=%s, провайдер Ahrefs=%s, прогонов одновременно=%s",
        config.storage.queue_name,
        config.ahrefs.provider,
        config.storage.worker_concurrency,
    )
    build_worker().work(with_scheduler=False)


if __name__ == "__main__":
    main()
