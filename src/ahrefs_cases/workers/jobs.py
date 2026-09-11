"""Фоновые задачи: прогон сбора и сборка пачки кейсов.

Задача живёт в другом процессе, поэтому у неё **своя** сессия и свои аргументы —
числа и строки. Ни сессия вызывающего, ни провайдер, ни собранный кейс сюда не
передаются: в режиме `redis` они просто не доедут.

**Упавшая задача обязана оставить след.** Наблюдателя снаружи у нас нет: реапер
зависших прогонов из CRM опирался на жёсткий таймаут RQ-джобы, а у нас прогон
идёт часами и такого таймаута нет (урок L24). Значит, отметить `failed` должна
сама задача, и именно поэтому здесь широкий `except` — с логом и записью, а не
с молчанием.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from ahrefs_cases.classify.windows import point_windows
from ahrefs_cases.collect.runner import collect_projects
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.session import dispose_engine, get_sessionmaker

logger = logging.getLogger(__name__)


def collect_job(run_id: int, refresh: bool = False) -> None:
    """Прогон сбора. `run_id` — прогон, уже созданный при постановке в очередь.

    `refresh` принимается **позиционно** нарочно: очередь пересылает аргументы
    задачи позиционным списком (`enqueue(job, *args)`), и у RQ они такими же
    уезжают через сериализацию. Объявленный только-ключевым, он давал
    `TypeError: collect_job() takes 1 positional argument but 2 were given` —
    задача не начиналась вовсе, а строка прогона оставалась `queued` навсегда и
    замком «один активный» блокировала все следующие запуски до реапера.
    """
    asyncio.run(_run_guarded(run_id, _collect(run_id, refresh=refresh)))


def cases_job(run_id: int) -> None:
    """Сборка пачки кейсов в ZIP по текущим вердиктам."""
    asyncio.run(_run_guarded(run_id, _pack()))


async def _collect(run_id: int, *, refresh: bool) -> str:
    """Прогон по уже открытому прогону: его создал обработчик запроса.

    Строку создаёт API, потому что только он знает, кто нажал кнопку; задача
    её продолжает, а не заводит вторую.
    """
    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
        projects = list((await session.execute(select(Project))).scalars().all())
        # Окна точек передаёт вызывающий: `collect` не знает про пороги по
        # контракту слоёв. Без них задача покупала бы бесплатный максимум под
        # минимальную цену запроса — то есть прогон, запущенный кнопкой, стоил
        # бы и собирал не то же, что прогон из консоли, и смета на экране
        # называла бы цену другого прогона.
        report = await collect_projects(
            session,
            projects,
            refresh=refresh,
            run=run,
            windows=await point_windows(session),
        )
        await session.commit()
    return f"собрано проектов: {report.projects_ok}, units: {report.units_spent}"


async def _pack() -> str:
    # Импорт внутри: `export` живёт слоем выше `workers` по контракту слоёв,
    # и тянуть его на уровень модуля значило бы связать воркер с рендером.
    from ahrefs_cases.cli.case_commands import pack_cases

    code = await pack_cases()
    return f"пачка кейсов собрана, код возврата {code}"


async def _run_guarded(run_id: int, work: object) -> None:
    """Выполнить работу и закрыть прогон — успехом или причиной падения."""
    try:
        summary = await work  # type: ignore[misc]
        await _finish(run_id, RunStatus.DONE, str(summary), only_if_open=True)
    except Exception as exc:
        logger.exception("job_failed", extra={"run_id": run_id})
        await _finish(run_id, RunStatus.FAILED, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        await dispose_engine()


async def _finish(run_id: int, status: RunStatus, note: str, *, only_if_open: bool = False) -> None:
    """Записать исход прогона. Отдельной сессией: прежняя могла умереть с задачей.

    `only_if_open` — для успешного пути: прогон сбора закрывает себя сам и
    может закончиться `partial` (часть доменов пропущена) или быть отклонён
    квотой. Переписывать такой исход на `done` значило бы стереть то, что
    журнал сказал честно.
    """
    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
        if run is None:
            logger.warning("job_finish_without_run", extra={"run_id": run_id})
            return
        if only_if_open and run.status not in (RunStatus.QUEUED, RunStatus.RUNNING):
            return
        run.status = status
        run.error = note if status is RunStatus.FAILED else ""
        await session.commit()
