"""Пересчёт вердиктов по указанной версии порогов и активация версии.

Зачем отдельно от классификации. Классификация отвечает на вопрос «какая группа
у этого проекта **сейчас**», пересчёт — на вопрос «какая была бы, если бы пороги
были другими». Второй вопрос задают на калибровке, и задают его десятки раз
подряд: заказчик правит пороги по 10 доменам с экспертной оценкой и смотрит,
что изменилось. Без пересчёта калибровка невозможна в принципе.

Ahrefs здесь не трогается вовсе — в этом и был смысл отделять классификацию от
сбора: смена порогов обязана быть бесплатной. Проверяется падающим `httpx`.

Прошлые вердикты остаются. Ключ `(project_id, ruleset_id)` из модели Ф1 делает
вердикты разных версий соседями, а не заменой друг друга: через полгода вопрос
«почему тогда было good» обязан иметь ответ.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify import verdicts as verdicts_module
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset


@dataclass(frozen=True, slots=True)
class Skipped:
    """Проект, которому этой версией порогов считать нечем."""

    domain: str
    reason: str


@dataclass(frozen=True, slots=True)
class RecalcReport:
    """Итог пересчёта в числах, которые показывают человеку.

    Считаются **проекты**, а не расчёты: у пересчёта они совпадают, но пропуск
    по нехватке данных легко посчитать отдельной сущностью и получить «проектов
    10, пересчитано 13» — число, которое человеку показать нельзя (урок L13).
    """

    version: str
    total: int
    by_group: dict[Group, int] = field(default_factory=dict)
    skipped: list[Skipped] = field(default_factory=list)

    @property
    def recalculated(self) -> int:
        return sum(self.by_group.values())

    def as_lines(self) -> list[str]:
        order = (Group.GOOD, Group.MEDIUM, Group.POOR, Group.INSUFFICIENT_DATA)
        counts = ", ".join(f"{group.value}: {self.by_group.get(group, 0)}" for group in order)
        lines = [
            f"пересчёт по версии {self.version}",
            f"проектов: {self.total} (пересчитано {self.recalculated}, "
            f"пропущено {len(self.skipped)})",
            counts,
        ]
        lines.extend(f"  пропущен {item.domain}: {item.reason}" for item in self.skipped)
        return lines


async def ruleset_by_version(session: AsyncSession, version: str) -> Ruleset:
    """Версия порогов по имени. Нет такой — ошибка со списком, а не пустота.

    Пустой результат на опечатку в версии выглядит как «нечего пересчитывать» и
    читается как успех: на калибровке это означает «я поправил пороги, ничего не
    изменилось» вместо «я ошибся в имени версии».
    """
    found = (
        await session.execute(select(Ruleset).where(Ruleset.version == version))
    ).scalar_one_or_none()
    if found is not None:
        return found

    available = (
        (await session.execute(select(Ruleset.version).order_by(Ruleset.id))).scalars().all()
    )
    known = ", ".join(available) if available else "ни одной"
    message = f"версии порогов {version!r} нет в базе. Доступны: {known}"
    raise ThresholdsError(message)


async def activate(session: AsyncSession, version: str) -> Ruleset:
    """Сделать версию действующей. Активная ровно одна.

    Активация **не** переписывает прошлые вердикты: она говорит, по какой версии
    считать следующие. Переписывать — значит потерять историю решений, ради
    которой вердикт и хранит `ruleset_id`.
    """
    target = await ruleset_by_version(session, version)
    for ruleset in (await session.execute(select(Ruleset))).scalars().all():
        ruleset.is_active = ruleset.id == target.id
    await session.flush()
    return target


async def recalc(
    session: AsyncSession,
    version: str,
    projects: Sequence[Project] | None = None,
    *,
    source: MetricSource,
) -> RecalcReport:
    """Пересчитать вердикты по версии порогов. Ahrefs не трогается.

    Проект, которому не хватает купленных месяцев под окна этой версии, **не
    получает вердикт** — он попадает в пропуски с названной нехваткой. Причина в
    `classify/coverage.py`: точка считается по тем месяцам окна, которые есть, и
    вердикт по половине окна выглядит настоящим.
    """
    ruleset = await ruleset_by_version(session, version)
    targets = list(projects) if projects is not None else await _all_projects(session)

    report = RecalcReport(version=ruleset.version, total=len(targets))
    for item in await verdicts_module.evaluate(session, targets, ruleset, source=source):
        if not item.has_data:
            report.skipped.append(Skipped(domain=item.project.domain, reason=item.gap.describe()))
            continue
        await verdicts_module.store(session, item.project, ruleset, item.computed)
        group = item.computed.decision.group
        report.by_group[group] = report.by_group.get(group, 0) + 1
    await session.flush()
    return report


async def _all_projects(session: AsyncSession) -> list[Project]:
    return list((await session.execute(select(Project))).scalars().all())
