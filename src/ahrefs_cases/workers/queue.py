"""Очередь задач: интерфейс и две реализации.

Тот же приём, что с провайдером Ahrefs, и по той же причине. На машине
разработчика Redis может не быть, а сервис обязан подниматься и работать;
`inline` выполняет задачу тут же, `redis` ставит её в RQ настоящему воркеру.
Выбор делает **конфиг**, а не тот, кто первым дошёл до очереди (урок L53).

Аргументы задач — простые значения: в режиме `redis` задача уезжает в другой
процесс через сериализацию, и объект сессии, провайдера или кейса туда не
доедет. Ограничение выглядит мелким ровно до первой попытки передать сессию.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import anyio.to_thread

from ahrefs_cases import config

logger = logging.getLogger(__name__)

JobArg = int | str | bool | None
"""Что можно передать задаче. Не «почти всё, лишь бы сериализовалось»: список
типов назван, чтобы нарушение было видно в подписи, а не в проде."""


class JobQueue(Protocol):
    """Куда ставится фоновая работа.

    Постановка асинхронная у обеих реализаций: `inline` выполняет задачу сразу
    и обязан не занимать цикл событий, а `redis` только пишет в очередь.
    """

    async def enqueue(self, job: Callable[..., object], *args: JobArg) -> str: ...


@dataclass(frozen=True, slots=True)
class InlineQueue:
    """Выполняет задачу немедленно, в вызывающем процессе.

    Не заглушка: это рабочий режим разработки. Поэтому и поведение при падении
    такое же, как у настоящей очереди: **вызывающий узнаёт, что задача
    поставлена, а не что она удалась**. Падение записывает сама задача (она
    закрывает прогон статусом `failed`), а здесь оно логируется и не
    превращается в `500` — иначе ответ API зависел бы от выбранного бэкенда.
    """

    async def enqueue(self, job: Callable[..., object], *args: JobArg) -> str:
        """Выполнить задачу в отдельном потоке и дождаться её.

        В потоке, а не прямо здесь: задача внутри поднимает свой цикл событий
        (`asyncio.run`), а вызов этого из уже работающего цикла — ошибка. То
        есть «выполнить сразу» и «выполнить в том же цикле» — разные вещи, и
        разницу видно только исполнением.
        """
        logger.info("job_inline_start", extra={"job": job.__name__})
        try:
            await anyio.to_thread.run_sync(job, *args)
        except Exception:
            logger.exception("job_inline_failed", extra={"job": job.__name__})
        return f"inline:{job.__name__}"


class RedisQueue:
    """Настоящая очередь RQ: задача уходит отдельному воркеру."""

    def __init__(self) -> None:
        from redis import Redis
        from rq import Queue

        self._queue = Queue(
            config.storage.queue_name,
            connection=Redis.from_url(config.storage.redis_url),
        )

    async def enqueue(self, job: Callable[..., object], *args: JobArg) -> str:
        enqueued = self._queue.enqueue(job, *args, job_timeout=_JOB_TIMEOUT_SEC)
        logger.info("job_enqueued", extra={"job": job.__name__, "job_id": enqueued.id})
        return str(enqueued.id)


_JOB_TIMEOUT_SEC = 4 * 60 * 60
"""Потолок времени задачи. Не оптимизм: прогон сотни доменов на живом API с
паузами между запросами идёт часами, и таймаут в минутах убивал бы оплаченную
работу на середине."""


def build_queue() -> JobQueue:
    """Очередь по конфигу. Одно место, где решается «сразу или воркером»."""
    return RedisQueue() if config.storage.queue_backend == "redis" else InlineQueue()
