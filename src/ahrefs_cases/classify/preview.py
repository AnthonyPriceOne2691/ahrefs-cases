"""Предпросмотр: кто сменит группу, если применить эту версию порогов.

Тот же вопрос, что у пересчёта, но без изменения состояния. На калибровке его
задают десятки раз подряд и обсуждают вдвоём-втроём: заказчик правит порог,
смотрит, спорит, правит снова. Отвечать на него записью вердиктов значит
смотреть на уже изменённое и откатывать руками.

**Расчёт здесь не свой.** Общий проход `verdicts.evaluate` считает вердикты и
проверяет покрытие, предпросмотр только сравнивает результат с тем, что человек
видит сейчас. Второй похожий расчёт разошёлся бы с пересчётом ровно тогда,
когда предпросмотру уже доверяют, — а доверять ему начнут на калибровке, где
цена ошибки это неверно утверждённый порог.

Три состояния, которые легко слить в одно «не изменится», и все три разные:
проект без вердикта (его ещё не классифицировали), проект с нехваткой купленных
месяцев (его этой версией считать нечем) и проект, который действительно
остался в своей группе. Молчание о первых двух читается как «всё в порядке».
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify import verdicts as verdicts_module
from ahrefs_cases.classify.recalc import Skipped, ruleset_by_version
from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict


@dataclass(frozen=True, slots=True)
class Change:
    """Проект, у которого группа изменится. `before is None` — вердикта ещё нет."""

    domain: str
    before: Group | None
    after: Group

    def as_line(self) -> str:
        was = self.before.value if self.before is not None else "нет вердикта"
        return f"  {self.domain}: {was} → {self.after.value}"


@dataclass(frozen=True, slots=True)
class PreviewReport:
    """Что изменится — и чего в этом счёте нет.

    Считаются **проекты**: пара групп «medium → good» может встретиться у
    десяти проектов, и счёт по парам дал бы число, которое человеку не
    показать (урок L13).
    """

    version: str
    total: int
    changes: tuple[Change, ...]
    first_time: tuple[Change, ...]
    unchanged: int
    missing_data: tuple[Skipped, ...]

    def directions(self) -> dict[str, int]:
        """Сводка «откуда куда», по убыванию количества и затем по имени.

        Порядок стабильный между запусками: два вывода калибровки сравнивают
        глазами, и прыгающие строки делают это невозможным.
        """
        counts: dict[str, int] = {}
        for change in self.changes:
            key = f"{change.before.value if change.before else '—'} → {change.after.value}"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

    def as_lines(self) -> list[str]:
        lines = [
            f"предпросмотр версии {self.version} (ничего не записано)",
            f"проектов: {self.total} (сменят группу {len(self.changes)}, "
            f"впервые получат вердикт {len(self.first_time)}, "
            f"без изменений {self.unchanged}, "
            f"не хватает данных {len(self.missing_data)})",
        ]
        if not self.changes and not self.first_time:
            # «Изменений нет» и «нечего показывать» читаются одинаково, а значат
            # разное: первое — ответ, второе — пустой список, за которым может
            # стоять ошибка в версии или пустая база.
            lines.append("изменений нет: эта версия порогов оставит все группы прежними")
        lines.extend(change.as_line() for change in self.changes)
        lines.extend(change.as_line() for change in self.first_time)
        if self.changes:
            directions = ", ".join(f"{key}: {count}" for key, count in self.directions().items())
            lines.append(f"направления: {directions}")
        lines.extend(
            f"  не хватает данных {item.domain}: {item.reason}" for item in self.missing_data
        )
        return lines


async def preview(
    session: AsyncSession,
    version: str,
    projects: Sequence[Project] | None = None,
    *,
    source: MetricSource,
) -> PreviewReport:
    """Что даст эта версия порогов. **Ничего не пишет** — ни вердиктов, ни статусов.

    «Было» берётся по **активной** версии, а не по последнему вердикту во
    времени: оператор сравнивает с тем, что видит на экране сегодня, а последним
    по времени может оказаться чужой эксперимент с третьей версией.
    """
    ruleset = await ruleset_by_version(session, version)
    targets = list(projects) if projects is not None else await _all_projects(session)
    current = await _active_groups(session)

    changes: list[Change] = []
    first_time: list[Change] = []
    missing: list[Skipped] = []
    unchanged = 0
    for item in await verdicts_module.evaluate(session, targets, ruleset, source=source):
        if not item.has_data:
            missing.append(Skipped(domain=item.project.domain, reason=item.gap.describe()))
            continue
        after = item.computed.decision.group
        before = current.get(item.project.id)
        if before is None:
            first_time.append(Change(domain=item.project.domain, before=None, after=after))
        elif before is not after:
            changes.append(Change(domain=item.project.domain, before=before, after=after))
        else:
            unchanged += 1

    return PreviewReport(
        version=ruleset.version,
        total=len(targets),
        changes=tuple(sorted(changes, key=lambda change: change.domain)),
        first_time=tuple(sorted(first_time, key=lambda change: change.domain)),
        unchanged=unchanged,
        missing_data=tuple(sorted(missing, key=lambda item: item.domain)),
    )


async def _active_groups(session: AsyncSession) -> dict[int, Group]:
    """Группы, которые человек видит сейчас: вердикты по активной версии."""
    stmt = (
        select(Verdict.project_id, Verdict.group)
        .join(Ruleset, Ruleset.id == Verdict.ruleset_id)
        .where(Ruleset.is_active.is_(True))
    )
    return {row.project_id: row.group for row in (await session.execute(stmt)).all()}


async def _all_projects(session: AsyncSession) -> list[Project]:
    return list((await session.execute(select(Project))).scalars().all())
