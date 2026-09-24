"""Журнал прогонов: кто запустил, что случилось с каждым проектом, во что обошлось.

Сбор — платная и падающая операция. Без журнала нельзя объяснить счёт от Ahrefs,
докрутить упавшие проекты и доверять числам в кейсе.

Пропуск с причиной — **штатный** исход, а не ошибка: молодой домен, домен без
истории, нехватка квоты. Прогон на сотню доменов, падающий из-за одного, не
собирает ничего.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.collect.budget import record_spend
from ahrefs_cases.collect.fetch import TaskOutcome
from ahrefs_cases.collect.series import store_history
from ahrefs_cases.storage._enums import ProjectStatus, RunItemOutcome, RunStatus, UserGroup
from ahrefs_cases.storage.models.project import Project
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


STAGE1 = "stage1"
STAGE2 = "stage2"
CASE_DATA = "case_data"
CASES = "cases"
"""Ступень прогона — в снимке параметров (`params_snapshot["stage"]`).

Журнал показывал все прогоны одинаково, и сборка кейсов без вердиктов читалась
как сбор «0 из 18, пропущено 18» (B6). Ступень пишется в снимок, а не колонкой:
это свойство прогона того же рода, что провайдер и группировка, и миграция ради
неё не нужна. У прогонов старше этого поля ступени нет — это «неизвестно»."""


async def open_run(
    session: AsyncSession,
    started_by: int,
    projects_total: int,
    *,
    stage: str = "",
    job_key: str = "",
) -> Run:
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
            "collect_scheme": config.ahrefs.collect_scheme,
            "fixture_seed": config.ahrefs.fixture_seed,
            "stage": stage,
            # Ключ задачи очереди — по нему реапер спрашивает, жива ли она.
            # Есть только у прогонов, поставленных через очередь: прогон из
            # консоли идёт без RQ, и «задачи нет в очереди» его не касается.
            **({"job": job_key} if job_key else {}),
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


_REASON_LIMIT = 400
"""Сколько символов отчёта об отказе показывать. `Run.error` — колонка `Text`,
ограничение не от базы: строку читают глазами в таблице прогонов, и трактат
там не читается."""


def failure_reason(exc: BaseException) -> str:
    """Отказ одной строкой — с первопричиной, а не только с последней ошибкой.

    Python хранит всю цепочку (`__cause__` / `__context__`), а в журнал до сих
    пор попадало одно исключение — то, которое поймали последним. Живой прогон
    13.09.2026 показал цену: задача упала `AttributeError` (у воркера в памяти
    был старый модуль конфига), запись причины упала следом `MissingGreenlet`,
    и в журнале осталась **вторая**. Оператор читает таблицу прогонов, видит
    ошибку про greenlet и чинит событийный цикл вместо перезапуска воркера.

    Правило: ошибка, случившаяся при обработке другой, почти всегда следствие.
    Называем обе — последнюю (она ближе к месту) и первую (она объясняет).
    """
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__

    last = f"{type(chain[0]).__name__}: {chain[0]}"
    if len(chain) == 1:
        return last[:_REASON_LIMIT]
    root = chain[-1]
    return f"{last} (первопричина — {type(root).__name__}: {root})"[:_REASON_LIMIT]


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


@dataclass(frozen=True, slots=True)
class ProjectFate:
    """Что случилось с одним проектом в прогоне — в человеческом виде."""

    domain: str
    outcome: RunItemOutcome
    reason: str
    units_actual: int
    project_deleted: bool = False
    """Проект удалён: ссылки у строки журнала нет, домен и расход остались."""


async def fates(session: AsyncSession, run_id: int, *, limit: int) -> list[ProjectFate]:
    """Судьбы проектов прогона: по одной на проект, а не на запрос.

    ТЗ требует «сколько обработано, сколько пропущено и почему». Записи для
    этого пишутся с Ф2, но наружу не отдавались: экран показывал «17 из 19» и
    молчал о двух — а пропуск бывает четырёх видов, и действия по ним разные
    (докупить историю, поправить строку списка, поднять лимит, перезапустить).

    Свёртка та же, что у итогов прогона (`_fold_by_project`): на шаге 2 у одного
    проекта четыре запроса, и счёт по задачам дал бы «проектов 3, пропущено 12»
    — число, которое человеку показать нельзя (урок L13). Причина берётся у той
    записи, которая исход и определила.

    `limit` обязателен: у прогона сотня проектов сегодня и неизвестно сколько
    завтра.
    """
    stmt = select(RunItem).where(RunItem.run_id == run_id).order_by(RunItem.id)
    items = (await session.execute(stmt)).scalars().all()
    decided = _fold_by_project(items)

    seen: dict[FateKey, ProjectFate] = {}
    for item in items:
        key = _fate_key(item)
        outcome = decided.get(key)
        if outcome is None or item.outcome is not outcome:
            continue
        previous = seen.get(key)
        seen[key] = ProjectFate(
            domain=item.raw_domain,
            outcome=outcome,
            reason=item.reason or (previous.reason if previous else ""),
            units_actual=(previous.units_actual if previous else 0) + item.units_actual,
            project_deleted=item.project_id is None,
        )
    return list(seen.values())[:limit]


FateKey = int | str  # номер проекта, а у удалённого — домен строки журнала


def _fate_key(item: RunItem) -> FateKey:
    """Удаление проекта обнуляет ссылку у строк журнала (`ON DELETE SET NULL`), и
    ключ по `project_id` сливал все удалённые проекты прогона в одну судьбу — с
    доменом первого и суммой units всех. Домен их разводит; две удалённые
    кампании одного сайта в одном прогоне развести нечем (граница, Z41)."""
    return item.project_id if item.project_id is not None else item.raw_domain


def _fold_by_project(items: Sequence[RunItem]) -> dict[FateKey, RunItemOutcome]:
    """Исход **проекта**, а не задачи.

    На шаге 2 у одного проекта четыре запроса, и подсчёт по задачам давал в
    отчёте «проектов 3, собрано 12» — число, которое нельзя показать человеку.
    Правило свёртки: одна упавшая задача делает проект упавшим (данные кейса
    неполны), иначе достаточно одной успешной.
    """
    folded: dict[FateKey, RunItemOutcome] = {}
    for item in items:
        key = _fate_key(item)
        current = folded.get(key)
        if current is RunItemOutcome.FAILED:
            continue
        if item.outcome is RunItemOutcome.FAILED or current is None:
            folded[key] = item.outcome
        elif current is not RunItemOutcome.OK and item.outcome is RunItemOutcome.OK:
            folded[key] = RunItemOutcome.OK
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


_PROJECT_STATUS_BY_OUTCOME = {
    RunItemOutcome.OK: ProjectStatus.COLLECTED,
    RunItemOutcome.SKIPPED_NO_DATA: ProjectStatus.SKIPPED,
    RunItemOutcome.FAILED: ProjectStatus.FAILED,
}
"""`SKIPPED_ABORTED` намеренно отсутствует: по такому домену мы ничего не
спрашивали, и менять его статус значило бы записать незнание как результат."""


async def store_outcome(session: AsyncSession, run: Run, item: TaskOutcome) -> int:
    """Записать исход одной задачи: точки, расход, строку журнала, статус проекта."""
    points = 0
    if item.result is not None:
        points = await store_history(session, item.task.project_id, item.result)
        await record_spend(session, run.id, item.result)
    await add_item(
        session,
        run,
        project_id=item.task.project_id,
        raw_domain=item.task.domain,
        outcome=item.outcome,
        reason=item.reason,
        units_actual=item.result.units_actual if item.result else 0,
    )
    await _apply_project_status(session, item)
    return points


async def _apply_project_status(session: AsyncSession, item: TaskOutcome) -> None:
    """Статус проекта по исходу сбора.

    Статус двигает прогон, а не приём списка (см. `intake/upsert.py`): иначе
    повторная загрузка файла обнуляла бы результат последнего сбора.
    """
    status = _PROJECT_STATUS_BY_OUTCOME.get(item.outcome)
    if status is None:
        return
    project = await session.get(Project, item.task.project_id)
    if project is not None:
        project.status = status
