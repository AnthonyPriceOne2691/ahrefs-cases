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
from sqlalchemy.sql.elements import ColumnElement

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

    Берутся **последние** `RunItem` проекта: память включается только после
    `AHREFS_EMPTY_CONFIRMATIONS` пустых ответов подряд. Одного мало — так же
    выглядят опечатка в домене и расхождение формы ответа с нашей спекой, и
    поверить с первого раза значит замолчать проблему на месяц. Если после
    пустых ответов домен успели собрать, память не действует вовсе.
    """
    needed = config.ahrefs.empty_confirmations
    stmt = (
        select(RunItem.outcome, Run.finished_at)
        .join(Run, Run.id == RunItem.run_id)
        .where(RunItem.project_id == project_id)
        .order_by(RunItem.id.desc())
        .limit(needed)
    )
    rows = (await session.execute(stmt)).all()
    if len(rows) < needed:
        return None
    if any(row.outcome is not RunItemOutcome.SKIPPED_NO_DATA for row in rows):
        return None
    finished_at: datetime | None = rows[0].finished_at
    return finished_at


def empty_is_remembered(checked_at: datetime | None, now: datetime | None = None) -> bool:
    """Ещё действует ли память о пустом ответе."""
    if checked_at is None or config.ahrefs.empty_retry_days == 0:
        return False
    moment = now or datetime.now(UTC)
    return moment - checked_at < timedelta(days=config.ahrefs.empty_retry_days)


async def window_is_covered(
    session: AsyncSession,
    project_id: int,
    metrics: Sequence[Metric],
    source: MetricSource,
    *,
    window_from: date,
    window_to: date,
    now: date,
) -> bool:
    """Куплено ли окно целиком. Решение по окну **бинарное**, и это не упрощение.

    Для истории есть смысл в инкрементальном `date_from` (`next_date_from`): там
    цена растёт со строками, и докупить три месяца дешевле, чем девятнадцать. Для
    окна точки это неверно: запрос на один месяц и на четыре стоит одинаково —
    50 units, минимум за запрос. Значит частично покрытое окно надо покупать
    целиком: экономии от сужения нет, а дыра внутри окна сдвинула бы точку.

    Watermark (`coverage`) здесь не годится принципиально. Он хранит **одну**
    границу «собрано по такой-то месяц», а в схеме «две точки» собраны два
    разъединённых окна: watermark от точки Б объявил бы купленным и всё, что
    между ними, и окно точки А не купили бы никогда. Поэтому вопрос задаётся
    по конкретному окну, а не по проекту.

    Текущий (незакрытый) месяц внутри окна учитывается тем же правилом, что в
    `next_date_from`: окно считается покрытым, только если данные свежее TTL.
    """
    if not metrics:
        return False

    stmt = (
        select(
            MetricPoint.metric,
            func.count(func.distinct(MetricPoint.point_date)).label("months"),
            func.max(MetricPoint.fetched_at).label("fetched_at"),
        )
        .where(*_in_window(project_id, metrics, source, window_from, window_to))
        .group_by(MetricPoint.metric)
    )
    rows = (await session.execute(stmt)).all()
    if len(rows) < len(set(metrics)):
        return False

    expected = _months_between(window_from, window_to)
    if any(row.months < expected for row in rows):
        return False
    if window_to <= closed_through(now):
        return True
    return is_fresh(min(row.fetched_at for row in rows))


def _months_between(window_from: date, window_to: date) -> int:
    """Сколько месячных строк ожидается в окне. Обе границы включительно."""
    months = (window_to.year - window_from.year) * 12 + (window_to.month - window_from.month)
    return max(1, months + 1)


def _in_window(
    project_id: int,
    metrics: Sequence[Metric],
    source: MetricSource,
    window_from: date,
    window_to: date,
) -> list[ColumnElement[bool]]:
    """Условие «точки этого проекта по этим метрикам внутри окна».

    Вынесено, потому что два вопроса к окну — «куплено ли целиком» и «чего не
    хватает» — задаются одним и тем же фильтром. Гейт копипаста поймал их на
    второй же функции; две копии условия разошлись бы при добавлении любого
    нового измерения (скажем, страны).
    """
    return [
        MetricPoint.project_id == project_id,
        MetricPoint.metric.in_(list(metrics)),
        MetricPoint.source == source,
        MetricPoint.point_date >= window_from,
        MetricPoint.point_date <= window_to,
    ]


async def missing_span(
    session: AsyncSession,
    project_id: int,
    metrics: Sequence[Metric],
    source: MetricSource,
    *,
    window_from: date,
    window_to: date,
) -> tuple[date, date] | None:
    """Какой отрезок окна не куплен. `None` — куплено всё.

    Существует из-за L27 и ступени кейса. После шага 2 у позиций есть первые и
    последние месяцы периода, а середины нет. `coverage` вернёт watermark по
    **последнему** месяцу, `next_date_from` скажет «докупать нечего», и кривая
    так и останется из двух точек — молча, потому что формально серия
    «собрана по декабрь».

    Возвращается **непрерывный** отрезок от первого недостающего месяца до
    последнего, даже если внутри что-то есть. Это сознательно дороже точного
    набора дыр: при построчном биллинге лишний месяц стоит одну строку, а
    дробление на отдельные запросы упирается в минимум 50 units за каждый — то
    есть выходит дороже на любом реалистичном числе дыр.
    """
    if not metrics:
        return None

    stmt = (
        select(MetricPoint.point_date)
        .where(*_in_window(project_id, metrics, source, window_from, window_to))
        .group_by(MetricPoint.point_date)
        .having(func.count(func.distinct(MetricPoint.metric)) >= len(set(metrics)))
    )
    present = {row.point_date for row in (await session.execute(stmt)).all()}
    missing = [month for month in _months_range(window_from, window_to) if month not in present]
    if not missing:
        return None
    return missing[0], missing[-1]


def _months_range(window_from: date, window_to: date) -> list[date]:
    """Месяцы окна, по первым числам."""
    months: list[date] = []
    cursor = _month_start(window_from)
    last = _month_start(window_to)
    while cursor <= last:
        months.append(cursor)
        cursor = _next_month(cursor)
    return months


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
