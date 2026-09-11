"""Пороги: версии, предпросмотр, активация, пересчёт.

Самое опасное место сервиса: одна цифра перекладывает по группам всю базу и
меняет, какие кейсы уйдут клиентам. По ТЗ пороги утверждают Head of Link
Building и Owner, пользователь их не правит — и ровно ради этого различия ТЗ
развело три группы доступа.

**Смотреть и применять — разные действия.** Пересчёт бесплатен: Ahrefs при
смене порогов не дёргается. Поэтому предпросмотр «кто сменит группу» открыт
праву `read`, а сохранение и активация — праву `edit_thresholds`.

**Версия неизменяема.** Правка — новая версия: вердикты ссылаются на версию, и
правка задним числом делает прошлые решения необъяснимыми.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import (
    MAX_PAGE,
    PreviewChange,
    PreviewView,
    RulesetCreate,
    RulesetRow,
)
from ahrefs_cases.classify import thresholds as thresholds_module
from ahrefs_cases.classify.preview import Change as PreviewItem
from ahrefs_cases.classify.preview import preview as preview_report
from ahrefs_cases.classify.recalc import activate, recalc
from ahrefs_cases.classify.rulesets import by_version
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.storage.models.ruleset import Ruleset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rulesets", tags=["rulesets"])

ReadDep = Annotated[object, Depends(require_right("read"))]
EditDep = Annotated[object, Depends(require_right("edit_thresholds"))]


@router.get("", response_model=list[RulesetRow])
async def list_rulesets(
    session: SessionDep,
    _: ReadDep = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
) -> list[RulesetRow]:
    """Версии порогов: их видят все, правят не все.

    Граница выдачи такая же, как у остальных списков: версий столько, сколько
    их утвердили люди, и это растущий набор — медленно, но без потолка.
    """
    stmt = select(Ruleset).order_by(Ruleset.id.desc()).limit(limit)
    return [
        RulesetRow(
            id=item.id,
            version=item.version,
            is_active=item.is_active,
            note=item.note,
            created_at=item.created_at,
            payload=item.payload,
        )
        for item in (await session.execute(stmt)).scalars().all()
    ]


@router.post("", response_model=RulesetRow, status_code=status.HTTP_201_CREATED)
async def save_ruleset(
    payload: RulesetCreate, session: SessionDep, _: EditDep = None
) -> RulesetRow:
    """Сохранить новую версию порогов. Активной она не становится.

    Сохранение и применение разнесены нарочно: иначе «посмотреть, что будет» и
    «сделать так» сливаются в один необратимый шаг.
    """
    if await by_version(session, payload.version) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"версия {payload.version} уже есть: правка порогов — это новая версия",
        )

    body: dict[str, Any] = {**payload.payload, "version": payload.version}
    try:
        parsed = thresholds_module.parse(body)
    except (ThresholdsError, ValueError) as exc:
        # Разбор моделью, а не запись JSONB как есть: чужая форма, попавшая в
        # базу, обнаружится на классификации — то есть уже на вердиктах (L23).
        # Имя константы — новое (`..._CONTENT`): старое объявлено устаревшим, а
        # `filterwarnings = ["error"]` превращает предупреждение в пятисотку
        # ровно на пути обработки ошибки.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    ruleset = Ruleset(
        version=parsed.version,
        payload=parsed.model_dump(mode="json"),
        is_active=False,
        note=payload.note,
    )
    session.add(ruleset)
    await session.flush()
    logger.info("ruleset_saved", extra={"version": ruleset.version})
    return RulesetRow(
        id=ruleset.id,
        version=ruleset.version,
        is_active=False,
        note=ruleset.note,
        created_at=ruleset.created_at,
        payload=ruleset.payload,
    )


@router.post("/{version}/preview", response_model=PreviewView)
async def preview_ruleset(version: str, session: SessionDep, _: ReadDep = None) -> PreviewView:
    """Кто сменит группу при этой версии. Ничего не записывает."""
    try:
        report = await preview_report(session, version)
    except ThresholdsError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PreviewView(
        version=report.version,
        total=report.total,
        changes=[_change(item) for item in report.changes],
        first_time=[_change(item) for item in report.first_time],
        unchanged=report.unchanged,
        missing_data=[item.domain for item in report.missing_data],
    )


@router.post("/{version}/activate", response_model=RulesetRow)
async def activate_ruleset(version: str, session: SessionDep, _: EditDep = None) -> RulesetRow:
    """Сделать версию действующей: следующая классификация пойдёт по ней."""
    try:
        ruleset = await activate(session, version)
    except ThresholdsError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    logger.info("ruleset_activated", extra={"version": version})
    return RulesetRow(
        id=ruleset.id,
        version=ruleset.version,
        is_active=True,
        note=ruleset.note,
        created_at=ruleset.created_at,
        payload=ruleset.payload,
    )


@router.post("/{version}/recalc")
async def recalc_ruleset(version: str, session: SessionDep, _: EditDep = None) -> dict[str, object]:
    """Пересчитать вердикты по версии. Ahrefs не трогается — это бесплатно."""
    try:
        report = await recalc(session, version)
    except ThresholdsError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"version": version, "lines": report.as_lines()}


def _change(item: PreviewItem) -> PreviewChange:
    return PreviewChange(
        domain=item.domain,
        was=item.before.value if item.before is not None else None,
        becomes=item.after.value,
    )
