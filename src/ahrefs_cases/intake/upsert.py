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
from ahrefs_cases.intake.rejections import Notice, RejectReason
from ahrefs_cases.storage.geo import WORLDWIDE_LABEL, ahrefs_country, label
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project


@dataclass(frozen=True, slots=True)
class UpsertResult:
    created: int
    updated: int
    project_ids: tuple[int, ...] = ()
    """Проекты этого источника — созданные и обновлённые, в порядке строк.
    По ним идёт цикл «по файлу» (решение владельца 25.09.2026): прогон и пачка
    — проекты загруженного списка, а не вся база."""

    notices: tuple[Notice, ...] = ()
    """Замечания обновления: первая страна сменилась, а ряды куплены по другой."""


async def upsert_projects(session: AsyncSession, drafts: list[ProjectDraft]) -> UpsertResult:
    """Черновики → проекты. Возвращает, сколько создано и сколько обновлено."""
    if not drafts:
        return UpsertResult(created=0, updated=0)

    existing = await _load_existing(session, drafts)
    bought = await _bought_countries(session, [project.id for project in existing.values()])
    created = 0
    updated = 0
    touched: list[Project] = []
    notices: list[Notice] = []
    for draft in drafts:
        project = existing.get(draft.key)
        if project is None:
            project = _to_project(draft)
            session.add(project)
            created += 1
        else:
            notice = _geo_changed(draft, project.geo, bought.get(project.id, set()))
            if notice is not None:
                notices.append(notice)
            _apply(project, draft)
            updated += 1
        touched.append(project)

    await session.flush()
    # Номера — после `flush`: у новых проектов их выдаёт база. Дважды один проект
    # (две одинаковые строки файла) — один номер.
    ids = tuple(dict.fromkeys(project.id for project in touched))
    return UpsertResult(created=created, updated=updated, project_ids=ids, notices=tuple(notices))


async def _bought_countries(session: AsyncSession, project_ids: list[int]) -> dict[int, set[str]]:
    """Страны купленных рядов по проектам — одним запросом на весь список."""
    if not project_ids:
        return {}
    stmt = (
        select(MetricPoint.project_id, MetricPoint.country)
        .where(MetricPoint.project_id.in_(project_ids))
        .distinct()
    )
    found: dict[int, set[str]] = {}
    for project_id, country in (await session.execute(stmt)).all():
        found.setdefault(project_id, set()).add(country)
    return found


def _geo_changed(draft: ProjectDraft, was: str, bought: set[str]) -> Notice | None:
    """Замечание, когда первая страна сменилась, а ряды куплены не по новой (Z53).

    Сбор их не перекупает (решение владельца 07.10.2026 — предупреждать): цифры остаются
    по стране рядов, пока их не купят заново. Сравнивается **страна рядов** с новой
    первой страной, а не старая страна с новой: вернуть проекту страну, по которой ряды
    куплены, — это не смена цифр, и замечание тогда врало бы.
    """
    now = ahrefs_country(draft.geo)
    others = sorted(bought - {now})
    if ahrefs_country(was) == now or not others:
        return None
    detail = f"{', '.join(_first(code) for code in others)} → {_first(now)}"
    return Notice(draft.row_no, "geo", RejectReason.GEO_CHANGED, detail)


def _first(code: str) -> str:
    return label(code) if code else WORLDWIDE_LABEL


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
        brief=dict(draft.brief),
    )


def _apply(project: Project, draft: ProjectDraft) -> None:
    """Обновляем поля из файла и только их — `status` принадлежит прогону.

    Два поля файл не переписывает целиком. **NDA** файл может поставить
    («нет» в `publishable`), а снять — нет: флажок «непубличный проект» в
    карточке ставят ради клиента, и повторная загрузка старого списка не должна
    молча открывать его домен (решение владельца 07.10.2026). **Бриф** файл
    дополняет: пустая ячейка — «нет сведений», а не «очистить», и дописанное в
    карточке переживает загрузку.
    """
    project.period_end = draft.period_end
    project.niche = draft.niche
    project.geo = draft.geo
    project.service_type = draft.service_type
    project.client = draft.client
    project.owner = draft.owner
    project.publishable = project.publishable and draft.publishable
    project.work_volume = draft.work_volume
    project.notes = draft.notes
    # Новый словарь, а не правка на месте: изменение внутри JSONB ORM не видит.
    project.brief = {**(project.brief or {}), **draft.brief}
