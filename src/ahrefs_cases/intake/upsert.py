"""Запись черновиков в базу: создать или обновить, но не удвоить.

Ключ — `(domain, target_mode, period_start)`, тот же, что в `UniqueConstraint`
модели. Один домен законно приходит дважды с разными периодами работ: это два
кейса. Один домен с тем же периодом — тот же проект, и повторная загрузка списка
обязана его обновить, а не создать второй (пример B5).

Записываем не «всё подряд», а поля из файла: `status` проекта живёт своей жизнью
(его двигает сбор и классификация), и перезапись его на `new` при каждой
загрузке списка потеряла бы результат прошлого прогона.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.intake.drafts import ProjectDraft
from ahrefs_cases.storage.models.project import Project


@dataclass(frozen=True, slots=True)
class UpsertResult:
    created: int
    updated: int


async def upsert_projects(session: AsyncSession, drafts: list[ProjectDraft]) -> UpsertResult:
    """Черновики → проекты. Возвращает, сколько создано и сколько обновлено."""
    if not drafts:
        return UpsertResult(created=0, updated=0)

    existing = await _load_existing(session, drafts)
    created = 0
    updated = 0
    for draft in drafts:
        project = existing.get(draft.key)
        if project is None:
            session.add(_to_project(draft))
            created += 1
        else:
            _apply(project, draft)
            updated += 1

    await session.flush()
    return UpsertResult(created=created, updated=updated)


async def _load_existing(
    session: AsyncSession, drafts: list[ProjectDraft]
) -> dict[tuple[str, object, object], Project]:
    """Одним запросом на весь список, а не запросом на строку.

    Сто отдельных `SELECT` работают и на ста строках незаметны — но список
    задуман расти, и «незаметно» здесь ровно до первой тысячи.
    """
    keys = [draft.key for draft in drafts]
    stmt = select(Project).where(
        tuple_(Project.domain, Project.target_mode, Project.period_start).in_(keys)
    )
    result = await session.execute(stmt)
    return {
        (project.domain, project.target_mode, project.period_start): project
        for project in result.scalars()
    }


def _to_project(draft: ProjectDraft) -> Project:
    return Project(
        domain=draft.domain,
        target_mode=draft.target_mode,
        period_start=draft.period_start,
        period_end=draft.period_end,
        niche=draft.niche,
        geo=draft.geo,
        service_type=draft.service_type,
        client=draft.client,
        owner=draft.owner,
        publishable=draft.publishable,
        work_volume=draft.work_volume,
        notes=draft.notes,
    )


def _apply(project: Project, draft: ProjectDraft) -> None:
    """Обновляем поля из файла и только их — `status` принадлежит прогону."""
    project.period_end = draft.period_end
    project.niche = draft.niche
    project.geo = draft.geo
    project.service_type = draft.service_type
    project.client = draft.client
    project.owner = draft.owner
    project.publishable = draft.publishable
    project.work_volume = draft.work_volume
    project.notes = draft.notes
