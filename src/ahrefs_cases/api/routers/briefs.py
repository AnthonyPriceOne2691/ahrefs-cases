"""Бриф копирайтеру: каталог полей шаблона и правка брифа проекта.

Каталог отдаёт сервер, а не держит экран: поля и списки описаны один раз
(`storage.brief`), и форма карточки, приём файла и лист PDF читают одно и то
же. Правка — под своим правом `edit_briefs` (у всех трёх групп, отбирается
лично): бриф заполняет специалист, который вёл проект, а не только инженер.

Флажок «непубличный проект / NDA» правится здесь же и пишет `publishable`
наоборот — второго поля под тот же смысл нет.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.storage.brief import (
    FIELDS,
    FIELDS_BY_KEY,
    SECTIONS,
    BriefRejected,
    normalize,
)
from ahrefs_cases.storage.models.project import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["briefs"])

EditDep = Annotated[object, Depends(require_right("edit_briefs"))]


class ChoiceView(BaseModel):
    key: str
    label: str


class BriefFieldView(BaseModel):
    key: str
    label: str
    section: str
    kind: str
    choices: list[ChoiceView]
    column: str
    """Колонка входного файла; пусто — поле правится только в карточке."""

    max_len: int


class BriefCatalog(BaseModel):
    sections: list[str]
    fields: list[BriefFieldView]


class BriefPatch(BaseModel):
    """Что поменять. Поле, которого нет в запросе, не трогается; пустая строка — очистить."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[str, str] = Field(default_factory=dict)
    nda: bool | None = None


class BriefView(BaseModel):
    project_id: int
    nda: bool
    fields: dict[str, str]


@router.get(
    "/brief-fields",
    response_model=BriefCatalog,
    dependencies=[Depends(require_right("read"))],
)
async def brief_fields() -> BriefCatalog:
    """Пункты шаблона по разделам — в порядке шаблона, со списками значений."""
    return BriefCatalog(
        sections=list(SECTIONS),
        fields=[
            BriefFieldView(
                key=field.key,
                label=field.label,
                section=field.section,
                kind=field.kind.value,
                choices=[ChoiceView(key=c.key, label=c.label) for c in field.choices],
                column=field.column,
                max_len=field.max_len,
            )
            for field in FIELDS
        ],
    )


@router.patch("/projects/{project_id}/brief", response_model=BriefView)
async def edit_brief(
    project_id: int, patch: BriefPatch, session: SessionDep, _: EditDep = None
) -> BriefView:
    """Записать поля брифа и флажок NDA. Не годится хоть одно — не пишется ничего.

    Отказ называет каждое негодное поле его подписью: человек правит форму по
    тексту, а не по коду ответа (уроки L32, L34).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"проекта {project_id} нет"
        )
    brief, problems = _merged(dict(project.brief or {}), patch.fields)
    if problems:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="; ".join(problems)
        )
    # Новый словарь, а не правка на месте: изменение внутри JSONB ORM не видит.
    project.brief = brief
    if patch.nda is not None:
        project.publishable = not patch.nda
    logger.info(
        "brief_updated",
        extra={"project_id": project_id, "fields": sorted(patch.fields), "nda": patch.nda},
    )
    return BriefView(project_id=project_id, nda=not project.publishable, fields=brief)


def _merged(brief: dict[str, str], changes: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Бриф с правками и список отказов. Значения в журнал не уходят — в них клиент."""
    problems: list[str] = []
    for key, raw in changes.items():
        field = FIELDS_BY_KEY.get(key)
        if field is None:
            problems.append(f"поля «{key}» в брифе нет")
            continue
        value = normalize(field, raw)
        if isinstance(value, BriefRejected):
            problems.append(f"{field.label}: {value.detail}")
        elif value:
            brief[key] = value
        else:
            brief.pop(key, None)
    return brief, problems
