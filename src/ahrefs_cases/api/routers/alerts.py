"""Алерты: поводы, о которых оператор должен узнать сам.

ТЗ просит мониторинг units прямо: «алерты при превышении + отчёт после каждого
прогона». Здесь сервис отвечает **состоянием** — остаток квоты, упавшие
прогоны, готовая пачка кейсов; доставка в Telegram или Asana приходит вместе с
настройкой каналов и в этой поставке не делается.

Пустой список — это ответ «поводов нет», а не тишина: разница между «проверили,
чисто» и «не проверяли» стоит ровно столько же, сколько в остальном сервисе.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ahrefs_cases import config
from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import AlertView
from ahrefs_cases.collect.factory import build_quota
from ahrefs_cases.storage import RunStatus
from ahrefs_cases.storage.models.case import CaseArtifact
from ahrefs_cases.storage.models.run import Run

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])

_RECENT_RUNS = 20


@router.get("", response_model=list[AlertView])  # unbounded-ok: набор не растёт с корпусом
async def alerts(
    session: SessionDep, _: Annotated[object, Depends(require_right("read"))] = None
) -> list[AlertView]:
    """Текущие поводы: остаток units, упавшие прогоны, готовая пачка.

    Границы выдачи здесь нет намеренно, и это не исключение из правила: список
    **считается**, а не читается. Остаток квоты даёт не больше одного повода,
    готовая пачка — один, упавшие прогоны берутся из последних двадцати. Потолок
    ответа — двадцать два, и он не зависит от того, сколько в базе проектов.
    """
    found: list[AlertView] = []
    found.extend(await _units_alert())
    found.extend(await _failed_runs(session))
    found.extend(await _ready_bundle(session))
    return found


async def _units_alert() -> list[AlertView]:
    """Мало units — предупреждение с числом, а не «проверьте квоту».

    Не узнали остаток — тоже повод: «остаток неизвестен» и «остатка хватает»
    различаются, и второе без первого — догадка.
    """
    try:
        left = await build_quota().units_left()
    except Exception as exc:
        logger.warning("остаток квоты не получен (%s): %s", type(exc).__name__, exc)
        return [
            AlertView(
                kind="units_unknown",
                severity="warning",
                message="остаток units не удалось узнать: проверьте доступ к Ahrefs",
            )
        ]

    minimum = config.ahrefs.units_min_left
    if left <= minimum:
        return [
            AlertView(
                kind="units_low",
                severity="critical",
                message=f"остаток units {left} при минимуме {minimum}: прогон не стартует",
            )
        ]
    return []


async def _failed_runs(session: SessionDep) -> list[AlertView]:
    """Упавшие прогоны последних двадцати: номер и причина."""
    stmt = select(Run).order_by(Run.id.desc()).limit(_RECENT_RUNS)
    runs = (await session.execute(stmt)).scalars().all()
    return [
        AlertView(
            kind="run_failed",
            severity="serious",
            message=f"прогон {run.id} упал: {run.error or 'причина не записана'}",
        )
        for run in runs
        if run.status is RunStatus.FAILED
    ]


async def _ready_bundle(session: SessionDep) -> list[AlertView]:
    """Готовая пачка кейсов — повод забрать, а не тревога."""
    artifact = (
        (
            await session.execute(
                select(CaseArtifact).order_by(CaseArtifact.built_at.desc()).limit(1)
            )
        )
        .scalars()
        .first()
    )
    if artifact is None:
        return []
    return [
        AlertView(
            kind="cases_ready",
            severity="good",
            message=f"готов кейс {artifact.filename} — проверьте перед публикацией",
        )
    ]
