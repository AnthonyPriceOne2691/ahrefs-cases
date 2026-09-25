"""Фоновые задачи: прогон сбора, шаг 2 с данными под кейс и сборка пачки кейсов.

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
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.classify.candidates import stage2_candidates
from ahrefs_cases.classify.rulesets import active_ruleset, seed_thresholds
from ahrefs_cases.classify.verdicts import ClassifyReport, classify_all
from ahrefs_cases.classify.windows import point_windows
from ahrefs_cases.collect.factory import build_provider
from ahrefs_cases.collect.run_journal import add_item, failure_reason, finish_run, start_run
from ahrefs_cases.collect.runner import collect_case_data, collect_projects, collect_stage2
from ahrefs_cases.logs import run_context
from ahrefs_cases.storage import Group, RunStatus
from ahrefs_cases.storage.locks import work_lock
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.verdict import Verdict
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


def stage2_job(run_id: int) -> None:
    """Шаг 2 по кандидатам, пересчёт групп и данные под кейс — вторая кнопка.

    Отдельной кнопкой, а не хвостом прогона сбора, по решению владельца
    24.09.2026 (B6): шаг 2 и ступень кейса — дорогие ступени воронки, и тратить
    на них units должно отдельное нажатие со своей сметой. К этому моменту
    кандидаты уже известны, поэтому смета точная, а не «на всякий случай».
    """
    asyncio.run(_run_guarded(run_id, _stage2(run_id)))


def cases_job(run_id: int) -> None:
    """Сборка пачки кейсов в ZIP по текущим вердиктам."""
    asyncio.run(_run_guarded(run_id, _pack(run_id)))


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
        # Классификация бесплатна — Ahrefs она не трогает, — и без неё прогон из
        # интерфейса кончался проектами без групп: «Проекты» пустые, собирать
        # кейсы не из чего (B6). Источник — режим провайдера: им же помечено
        # только что купленное.
        groups = await _classify(session)
    return f"собрано проектов: {report.projects_ok}, units: {report.units_spent}; " + "; ".join(
        groups.as_lines()
    )


async def _classify(session: AsyncSession) -> ClassifyReport:
    report = await classify_all(session, source=build_provider().source)
    await session.commit()
    return report


async def _stage2(run_id: int) -> str:
    """Кандидаты → шаг 2 → группы заново → данные под кейс тем, у кого он будет.

    Шаг 2 продолжает прогон, открытый API. Ступень кейса — своя строка журнала
    на того же автора: это второй сбор со своей ценой и своими исходами, и
    склеивать их в один прогон значило бы дважды записать каждый домен.
    """
    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
        source = build_provider().source
        windows = await point_windows(session)
        projects = list((await session.execute(select(Project))).scalars().all())
        candidates = await stage2_candidates(session, projects, source=source)
        if run is not None:
            run.projects_total = len(candidates)
            await session.commit()
        if not candidates:
            return "кандидатов нет: шаг 2 не нужен — за «плохих» дорогие метрики не платятся"

        second = await collect_stage2(session, candidates, run=run, windows=windows)
        await session.commit()
        groups = await _classify(session)
        chosen = await _with_case(session)
        lines = [
            f"шаг 2: собрано {second.projects_ok} из {len(candidates)}, units {second.units_spent}",
            *groups.as_lines(),
        ]
        if not chosen:
            return "; ".join([*lines, "данных под кейс не нужно: хороших и средних нет"])
        # Ключ задачи — тот же: ступень кейса идёт в той же задаче очереди, и
        # убитая выкаткой, она должна закрываться реапером так же, как шаг 2.
        case = await collect_case_data(
            session,
            chosen,
            windows=windows,
            started_by=run.started_by if run else None,
            job_key=str((run.params_snapshot or {}).get("job", "")) if run else "",
        )
        await session.commit()
        # Ещё один пересчёт — бесплатный и обязательный: ступень кейса купила DR
        # и стоимость трафика, кейс их напечатает, а сверка свежести считает
        # метрику, которой нет у вердикта, расхождением. Без этого каждый кейс
        # из интерфейса выходил «устаревшим» с рождения и не скачивался.
        await _classify(session)
    return "; ".join(
        [*lines, f"данные под кейс: {case.projects_ok} из {len(chosen)}, units {case.units_spent}"]
    )


async def _with_case(session: AsyncSession) -> list[int]:
    """Проекты, которым кейс положен: `good` и `medium` по действующей версии."""
    ruleset = await active_ruleset(session)
    stmt = select(Verdict.project_id).where(
        Verdict.ruleset_id == ruleset.id, Verdict.group.in_([Group.GOOD, Group.MEDIUM])
    )
    return list((await session.execute(stmt)).scalars().all())


async def _pack(run_id: int) -> str:
    """Сборка кейсов кнопкой: пачка, строки `cases` и судьба каждого проекта.

    Судьбы пишутся строками журнала в той же транзакции, что кейсы, и прогон
    закрывается `finish_run` — теми же итогами по строкам, что у сбора. Пока
    задача получала от сборки только код возврата, журнал на проде 24.09.2026
    говорил «собрано 0, пропущено 53» при десяти кейсах, а сводка жила в логе
    воркера (Z46, урок L130).
    """
    # Импорт внутри: `export` живёт слоем выше `workers` по контракту слоёв,
    # и тянуть его на уровень модуля значило бы связать воркер с рендером.
    from ahrefs_cases.cli.case_commands import case_fates, pack_built
    from ahrefs_cases.export.archive import pack_stamp

    async with get_sessionmaker()() as session:
        run = await session.get(Run, run_id)
        # Отметка о начале — здесь, а не в `_run_guarded`: у сбора её ставит сам
        # прогон после preflight, и отмеченный раньше он соврал бы, если квота
        # откажет. У сборки кейсов preflight нет, и без этой строки журнал
        # показывал её без времени начала и конца (B6).
        if run is not None:
            await start_run(session, run)
            await session.commit()
        # Отпечаток свежей пачки — до сборки: по нему видно, собрала ли она
        # свою (правило 19в `case-content.md`).
        before = await asyncio.to_thread(pack_stamp, config.export.output_dir)
        await seed_thresholds(session)
        # Ряды — режима провайдера, тем же источником, что классифицирует
        # `_classify`: кнопка и консоль собирают по одним данным (урок L63).
        result = await pack_built(session, build_provider().source)
        kept = await _keep_pack(run, run_id, before)
        if run is not None:
            for fate in case_fates(result):
                await add_item(
                    session,
                    run,
                    project_id=fate.project_id,
                    raw_domain=fate.domain,
                    outcome=fate.outcome,
                    reason=fate.reason,
                )
            run.projects_total = len(result.report.attempts)
            await finish_run(session, run)
        await session.commit()
    summary = "; ".join(result.lines())
    if kept:
        summary = f"{summary}; копия прогона: {kept}"
    logger.info("cases_packed", extra={"run_id": run_id, "summary": summary})
    return summary


async def _keep_pack(run: Run | None, run_id: int, before: tuple[Path, int] | None) -> str | None:
    """Отложить копию пачки этой сборки и записать её путь в снимок прогона.

    Копия нужна кнопке «Скачать» в строке журнала: пачка дня одна, следующая
    сборка её перепишет, а прогон отдаёт то, что собрал сам. Снимок правится
    в сессии сборки и уходит одной транзакцией с судьбами и закрытием
    прогона: экран перестаёт опрашивать прогон, как только тот закончился, и
    записанная следом копия осталась бы без кнопки до перезагрузки.

    Не отложилась (нет места, нет прав на томе) — сборка остаётся сборкой:
    пачка на «Кейсах» цела, прогон — без копии, лог называет номер прогона.
    """
    from ahrefs_cases.export.archive import keep_run_pack

    try:
        kept = await asyncio.to_thread(keep_run_pack, config.export.output_dir, run_id, before)
    except OSError:
        logger.exception("run_pack_not_kept", extra={"run_id": run_id})
        return None
    if kept is None:
        return None
    if run is not None:
        # JSONB: правка словаря на месте сессии не видна — заменяется целиком.
        run.params_snapshot = {
            **(run.params_snapshot or {}),
            "pack": kept.path,
            "pack_cases": kept.cases,
        }
    return kept.path


async def _run_guarded(run_id: int, work: object) -> None:
    """Выполнить работу и закрыть прогон — успехом или причиной падения.

    Всё внутри помечается идентификатором прогона: задачи идут параллельно,
    и без метки их строки в логе не разделить. Ручной `extra={"run_id": …}`
    ниже оставлен намеренно — он не мешает и читается на месте.

    Вся работа — под замком работы, и хвост после `finish_run` тоже: задача ещё
    раздаёт месяцы кампаниям и пересчитывает группы, и удаление проекта в нём
    уронило бы её, а `_finish` переписал бы честный `done` в `failed`.
    """
    with run_context(run_id):
        try:
            async with work_lock():
                summary = await work  # type: ignore[misc]
            await _finish(run_id, RunStatus.DONE, str(summary), only_if_open=True)
        except Exception as exc:
            logger.exception("job_failed", extra={"run_id": run_id})
            await _finish(run_id, RunStatus.FAILED, failure_reason(exc))
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
        if run.finished_at is None:
            run.finished_at = datetime.now(UTC)
        await session.commit()
