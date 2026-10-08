"""Выполнение задач прогона сбора: параллель, предохранитель, лимит времени, чекпойнты, остановка.

Отдельным модулем, потому что это одна работа со своими правилами, а `runner` — про то, какой прогон
открыть и по каким проектам: вместе они упёрлись в предел длины файла (урок L50). Правила здесь
денежные: задача, не остановленная вовремя, покупает ряды, которые никто не запишет (Z52).
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.breaker import ConsecutiveFailureBreaker
from ahrefs_cases.collect.fetch import TaskOutcome, fetch_one
from ahrefs_cases.collect.plan import CollectTask
from ahrefs_cases.collect.provider import AhrefsProvider
from ahrefs_cases.collect.run_journal import store_outcome
from ahrefs_cases.storage._enums import RunItemOutcome
from ahrefs_cases.storage.models.run import Run


async def execute_tasks(
    session: AsyncSession,
    engine: AhrefsProvider,
    run: Run,
    tasks: Sequence[CollectTask],
) -> int:
    """Выполнить задачи, записывая результат **по мере готовности**.

    Ф2а писала всё после `gather`: прогон, убитый на семидесятом домене, терял
    данные шестидесяти девяти, за которые units уже списаны. Здесь каждая
    завершённая задача попадает в базу сразу, а каждые
    `COLLECT_CHECKPOINT_EVERY` задач фиксируются коммитом.

    Возобновления как отдельного механизма не нужно: следующий прогон увидит
    собранное через кэш и докупит только остаток. Сбой записи или отмена
    прогона отменяет все незавершённые задачи до того, как ошибка пойдёт
    дальше: ни одна не переживает прогон и не начинает новый запрос (Z52).
    """
    semaphore = asyncio.Semaphore(config.ahrefs.max_parallel)
    breaker = ConsecutiveFailureBreaker(limit=config.ahrefs.breaker_max_failures)
    deadline = asyncio.get_running_loop().time() + config.ahrefs.run_timeout_sec
    """Прогон обязан закончиться до дедлайна.

    Не для красоты: реапер судит о смерти прогона по возрасту, и это верно
    только пока живой прогон физически не может идти дольше своего лимита. В
    CRM гарантию давал таймаут RQ-джобы, у нас до Ф5 очереди нет — значит
    лимит держит сам прогон (Z1 в docs/FINDINGS.md).
    """

    async def one(task: CollectTask) -> TaskOutcome:
        """Одна задача под семафором.

        Предохранитель проверяется и обновляется **внутри** семафора, а не в
        цикле потребления результатов. Снаружи это не работает: `as_completed`
        стартует все корутины сразу, проверка успевает пройти до первой
        неудачи, и предохранитель не срабатывает вообще — поймано тестом C14,
        который до этой правки видел 10 запросов вместо 3.

        Перелёт на величину `max_parallel` остаётся: задачи, уже ушедшие в
        сеть, не отзываются. Это цена параллельности, а не дефект.
        """
        async with semaphore:
            if breaker.tripped:
                return TaskOutcome(
                    task=task, outcome=RunItemOutcome.SKIPPED_ABORTED, reason=breaker.reason()
                )
            if asyncio.get_running_loop().time() >= deadline:
                return TaskOutcome(
                    task=task,
                    outcome=RunItemOutcome.SKIPPED_ABORTED,
                    reason=(
                        f"прогон превысил лимит {config.ahrefs.run_timeout_sec} с и остановлен. "
                        "Запрос по этому домену не делался; собранное сохранено, "
                        "повторный запуск догрузит остаток."
                    ),
                )
            outcome = await fetch_one(engine, task)
            breaker.record(ok=outcome.outcome is not RunItemOutcome.FAILED)
            return outcome

    running = [asyncio.create_task(one(task)) for task in tasks]
    points = 0
    try:
        for done, future in enumerate(asyncio.as_completed(running), start=1):
            item = await future
            points += await store_outcome(session, run, item)
            if done % config.ahrefs.checkpoint_every == 0:
                # Чекпойнт: прогон, убитый после этой точки, теряет не больше
                # `checkpoint_every` доменов — за них уже заплачено.
                await session.commit()
    except BaseException:
        # Сбой прогона — конец покупок (Z52): задачи созданы на весь список сразу,
        # и без отмены они покупали бы ряды, которые уже некому записать. Ушедшие
        # в сеть отменяются тоже: сессия после сбоя не примет их ответ.
        for pending in running:
            pending.cancel()
        await asyncio.gather(*running, return_exceptions=True)
        raise

    await session.commit()
    return points
