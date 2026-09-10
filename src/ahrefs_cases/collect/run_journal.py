"""Журнал прогонов: кто запустил, что случилось с каждым проектом, во что обошлось.

Сбор — платная и падающая операция. Без журнала нельзя объяснить счёт от Ahrefs,
докрутить упавшие проекты и доверять числам в кейсе.

Пропуск с причиной — **штатный** исход, а не ошибка: молодой домен, домен без
истории, нехватка квоты. Прогон на сотню доменов, падающий из-за одного, не
собирает ничего.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.storage._enums import RunItemOutcome, RunStatus, UserGroup
from ahrefs_cases.storage.models.run import Run, RunItem
from ahrefs_cases.storage.models.user import User

SYSTEM_USER_EMAIL = "cli@local"
_UNUSABLE_PASSWORD_HASH = "!"  # noqa: S105 — не секрет, а заведомо несовпадающий хеш
"""Не хеш вообще: bcrypt такой строки не породит, и сверка с ней не пройдёт
никогда. Вместе с `is_active=False` это значит, что системным пользователем
нельзя войти — он существует только чтобы у прогона был автор."""


async def system_user(session: AsyncSession) -> User:
    """Автор прогонов, запущенных из командной строки.

    `Run.started_by` не nullable, и делать его nullable ради Ф2а значило бы
    ослабить схему до появления авторизации (Ф5) — а потом уже не вернуть:
    строки с `NULL` останутся. Системный пользователь дешевле и честнее.
    """
    existing = await session.execute(select(User).where(User.email == SYSTEM_USER_EMAIL))
    user = existing.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        email=SYSTEM_USER_EMAIL,
        full_name="Прогон из командной строки",
        password_hash=_UNUSABLE_PASSWORD_HASH,
        group=UserGroup.ENGINEER,
        is_active=False,
    )
    session.add(user)
    await session.flush()
    return user


async def open_run(session: AsyncSession, started_by: int, projects_total: int) -> Run:
    """Открыть прогон в статусе `queued` и записать, чем он считается.

    Именно `queued`, а не `running`: между открытием и первым запросом стоит
    preflight по квоте, и прогон, отклонённый им, никогда не был запущен.
    Записывать его как `running` значило бы соврать журналу.

    Снимок параметров обязателен: через полгода вопрос «почему у кейса такие
    числа» упирается в провайдера, группировку и глубину истории, а они
    меняются конфигом.
    """
    run = Run(
        started_by=started_by,
        status=RunStatus.QUEUED,
        projects_total=projects_total,
        params_snapshot={
            "provider": config.ahrefs.provider,
            "history_grouping": config.ahrefs.history_grouping,
            "max_history_months": config.ahrefs.max_history_months,
            "fixture_seed": config.ahrefs.fixture_seed,
        },
    )
    session.add(run)
    await session.flush()
    return run


async def start_run(session: AsyncSession, run: Run) -> None:
    """Прогон прошёл preflight и начинает работу."""
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await session.flush()


async def reject_run(session: AsyncSession, run: Run, reason: str) -> None:
    """Прогон не начат: квоты нет или остаток неизвестен.

    Это штатный исход, а не сбой: причина пишется в `Run.error` и показывается
    оператору. `failed` без причины выглядел бы как поломка сервиса.
    """
    run.status = RunStatus.FAILED
    run.finished_at = datetime.now(UTC)
    run.error = reason
    await session.flush()


async def add_item(
    session: AsyncSession,
    run: Run,
    *,
    project_id: int,
    raw_domain: str,
    outcome: RunItemOutcome,
    reason: str = "",
    units_actual: int = 0,
) -> None:
    """Судьба одного проекта в прогоне."""
    session.add(
        RunItem(
            run_id=run.id,
            project_id=project_id,
            raw_domain=raw_domain,
            outcome=outcome,
            reason=reason,
            units_actual=units_actual,
        )
    )


async def count_outcome(session: AsyncSession, run_id: int, outcome: RunItemOutcome) -> int:
    """Сколько задач прогона закончились этим исходом.

    Запросом к журналу, а не счётчиком в памяти: то же правило, что у итогов в
    `finish_run` — число, показанное человеку, берётся оттуда же, откуда
    объясняется счёт.
    """
    stmt = select(func.count()).where(RunItem.run_id == run_id, RunItem.outcome == outcome)
    return int((await session.execute(stmt)).scalar_one())


async def finish_run(session: AsyncSession, run: Run, *, error: str = "") -> Run:
    """Закрыть прогон, посчитав итоги по его же записям.

    Итоги считаются из `RunItem`, а не накапливаются в переменных: сумма,
    посчитанная по дороге, расходится с журналом при первом же исключении в
    середине — и расхождение обнаруживается на экране расхода, где уже поздно.
    """
    items = (await session.execute(select(RunItem).where(RunItem.run_id == run.id))).scalars().all()
    by_project = _fold_by_project(items)
    run.projects_ok = sum(1 for outcome in by_project.values() if outcome is RunItemOutcome.OK)
    run.projects_failed = sum(
        1 for outcome in by_project.values() if outcome is RunItemOutcome.FAILED
    )
    run.units_actual = sum(item.units_actual for item in items)
    run.finished_at = datetime.now(UTC)
    run.error = error
    aborted = sum(1 for outcome in by_project.values() if outcome is RunItemOutcome.SKIPPED_ABORTED)
    run.status = _verdict(run, error=error, aborted=aborted)
    await session.flush()
    return run


def _fold_by_project(items: Sequence[RunItem]) -> dict[int | None, RunItemOutcome]:
    """Исход **проекта**, а не задачи.

    На шаге 2 у одного проекта четыре запроса, и подсчёт по задачам давал в
    отчёте «проектов 3, собрано 12» — число, которое нельзя показать человеку.
    Правило свёртки: одна упавшая задача делает проект упавшим (данные кейса
    неполны), иначе достаточно одной успешной.
    """
    folded: dict[int | None, RunItemOutcome] = {}
    for item in items:
        current = folded.get(item.project_id)
        if current is RunItemOutcome.FAILED:
            continue
        if item.outcome is RunItemOutcome.FAILED or current is None:
            folded[item.project_id] = item.outcome
        elif current is not RunItemOutcome.OK and item.outcome is RunItemOutcome.OK:
            folded[item.project_id] = RunItemOutcome.OK
    return folded


def _verdict(run: Run, *, error: str, aborted: int = 0) -> RunStatus:
    """`done`, `partial` или `failed` — три разных исхода, а не «успех/провал».

    Прогон, где половина доменов пропущена без данных, завершился успешно, но
    сказать «done» о нём нельзя: человек должен увидеть разницу до того, как
    начнёт собирать кейсы.

    Невыполненные задачи (предохранитель, лимит времени) делают прогон
    `partial` наравне с упавшими. Без этого прогон, где **ни одна** задача не
    выполнялась, отчитывался `done` — поймано слабым утверждением в тесте
    лимита времени: «done или partial» вместо конкретного ожидания и было
    признаком, что поведение не продумано.
    """
    if error:
        return RunStatus.FAILED
    if run.projects_failed or aborted:
        return RunStatus.PARTIAL
    return RunStatus.DONE
