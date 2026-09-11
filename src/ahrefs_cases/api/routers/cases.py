"""Библиотека кейсов и скачивание файла.

Файл лежит на диске, в базе — путь и контрольная сумма. Поэтому «кейс есть» и
«файл есть» это два разных вопроса, и ответ на второй бывает отрицательным:
каталог выгрузки переносят и чистят. Пустой ответ с кодом 200 в этом случае
неотличим от «кейса нет» — отдаём `404` (тот же класс, что урок L1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import MAX_PAGE, CaseRow
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.project import Project

router = APIRouter(
    prefix="/api/cases",
    tags=["cases"],
    dependencies=[Depends(require_right("read"))],
)


@router.get("", response_model=list[CaseRow])
async def list_cases(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CaseRow]:
    """Библиотека: свежие версии сверху — их и показывают первыми."""
    stmt = (
        select(Case, Project, CaseArtifact)
        .join(Project, Project.id == Case.project_id)
        .outerjoin(CaseArtifact, CaseArtifact.case_id == Case.id)
        .order_by(Case.created_at.desc(), Case.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        CaseRow(
            id=case.id,
            project_id=case.project_id,
            domain=project.domain,
            version=case.version,
            anonymized=case.anonymized,
            status=case.status.value,
            created_at=case.created_at,
            filename=artifact.filename if artifact is not None else None,
            checksum=artifact.checksum if artifact is not None else None,
        )
        for case, project, artifact in (await session.execute(stmt)).all()
    ]


@router.get("/{case_id}/download")
async def download_case(case_id: int, session: SessionDep) -> FileResponse:
    """Отдать файл кейса под тем именем, под которым он уйдёт клиенту."""
    artifact = (
        (
            await session.execute(
                select(CaseArtifact)
                .where(CaseArtifact.case_id == case_id)
                .order_by(CaseArtifact.built_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"у кейса {case_id} нет артефакта"
        )

    path = Path(artifact.path)
    # Проверка файла — обращение к диску: в асинхронном обработчике оно уходит
    # в поток, иначе один медленный том останавливает весь цикл событий.
    if not await anyio.to_thread.run_sync(path.is_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"файл кейса не найден на диске: {artifact.filename}",
        )
    return FileResponse(path, filename=artifact.filename, media_type="application/pdf")
