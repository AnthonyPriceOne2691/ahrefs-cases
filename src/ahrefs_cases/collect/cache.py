"""Кэш серий: что уже куплено и до какого месяца.

Главный рычаг экономии проекта. Отличие от обычного кэша «текущего состояния»,
где TTL — компромисс между свежестью и ценой: наши данные историчны.
**Закрытый месяц не меняется никогда**, поэтому TTL по времени для него
бессмыслен; неполный текущий месяц живёт TTL порядка суток.

Отдельного хранилища нет: кэш — это вопрос к `MetricPoint`. Второе хранилище
означало бы два источника правды о том, за что уже заплачено, и при их
расхождении непонятно, какой прав, — а платим мы по второму.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.storage._enums import Metric, MetricSource, RunItemOutcome
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.run import Run, RunItem


@dataclass(frozen=True, slots=True)
class Coverage:
    """До какой даты серия собрана и когда её последний раз трогали.

    `last_point` — **минимум** по метрикам endpoint'а, а не максимум: если
    `org_traffic` собран по май, а `org_cost` по апрель, докупать надо с апреля.
    Максимум оставил бы `org_cost` без мая навсегда — и дыра выглядела бы как
    отсутствие данных у Ahrefs.
    """

    last_point: date | None
    fetched_at: datetime | None

    @property
    def is_empty(self) -> bool:
        return self.last_point is None


async def coverage(
    session: AsyncSession,
    project_id: int,
    metrics: Sequence[Metric],
    source: MetricSource,
) -> Coverage:
    """Что уже есть в базе по этим метрикам этого проекта."""
    if not metrics:
        return Coverage(last_point=None, fetched_at=None)

    stmt = (
        select(
            MetricPoint.metric,
            func.max(MetricPoint.point_date).label("last_point"),
            func.max(MetricPoint.fetched_at).label("fetched_at"),
        )
        .where(
            MetricPoint.project_id == project_id,
            MetricPoint.metric.in_(list(metrics)),
            MetricPoint.source == source,
        )
        .group_by(MetricPoint.metric)
    )
    rows = (await session.execute(stmt)).all()
    if len(rows) < len(set(metrics)):
        # Хотя бы одной метрики нет вовсе — считать серию собранной нельзя.
        return Coverage(last_point=None, fetched_at=None)

    return Coverage(
        last_point=min(row.last_point for row in rows),
        fetched_at=max(row.fetched_at for row in rows),
    )


async def empty_since(session: AsyncSession, project_id: int) -> datetime | None:
    """Когда по проекту последний раз получили пустую историю — если это
    по-прежнему его последний известный исход.

    Зачем отдельный вопрос: домен без данных не оставляет ни одной точки, и
    обычный кэш о нём не знает ничего. Без этой памяти десять молодых доменов
    в списке покупают одну и ту же пустоту каждый месяц.

    Берётся **последний** `RunItem` проекта: если после пустого ответа домен
    успели собрать, память о пустоте больше не действует.
    """
    stmt = (
        select(RunItem.outcome, Run.finished_at)
        .join(Run, Run.id == RunItem.run_id)
        .where(RunItem.project_id == project_id)
        .order_by(RunItem.id.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None or row.outcome is not RunItemOutcome.SKIPPED_NO_DATA:
        return None
    finished_at: datetime | None = row.finished_at
    return finished_at


def empty_is_remembered(checked_at: datetime | None, now: datetime | None = None) -> bool:
    """Ещё действует ли память о пустом ответе."""
    if checked_at is None or config.ahrefs.empty_retry_days == 0:
        return False
    moment = now or datetime.now(UTC)
    return moment - checked_at < timedelta(days=config.ahrefs.empty_retry_days)


def closed_through(now: date) -> date:
    """Последний месяц, который считается окончательным.

    Все месяцы до текущего календарного. Граница считается от `now`,
    переданного параметром: `date.today()` внутри сделал бы поведение
    непроверяемым иначе как подкруткой системных часов.

    Оговорка честная: закрыт ли месяц с точки зрения самого Ahrefs — вопрос к
    живому ключу (Ф7). До тех пор правило календарное.
    """
    return date(now.year, now.month, 1) - timedelta(days=1)


def is_fresh(fetched_at: datetime | None, now: datetime | None = None) -> bool:
    """Свежа ли последняя загрузка по TTL текущего месяца."""
    if fetched_at is None:
        return False
    moment = now or datetime.now(UTC)
    return moment - fetched_at < timedelta(hours=config.ahrefs.current_month_ttl_hours)


def next_date_from(
    known: Coverage,
    *,
    window_from: date,
    window_to: date,
    now: date,
    fresh: bool,
) -> date | None:
    """С какого месяца докупать историю. `None` — не докупать вовсе.

    Три случая, и они разные по деньгам:

    1. в базе пусто → берём всё окно;
    2. собрано по закрытый месяц включительно → берём со следующего месяца;
    3. собран и текущий месяц → перезапрашиваем **только его**, и только если
       истёк TTL: текущий месяц меняется, но не ежеминутно.
    """
    if known.is_empty or known.last_point is None:
        return window_from

    closed = closed_through(now)
    if known.last_point < closed:
        candidate = _next_month(known.last_point)
    elif fresh:
        return None
    else:
        candidate = _month_start(known.last_point)

    if candidate > window_to:
        return None
    return max(candidate, window_from)


def _month_start(anchor: date) -> date:
    return date(anchor.year, anchor.month, 1)


def _next_month(anchor: date) -> date:
    total = anchor.year * 12 + anchor.month  # +1 месяц с нулевой базы
    return date(total // 12, total % 12 + 1, 1)
