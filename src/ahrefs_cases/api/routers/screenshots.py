"""Скриншоты проекта: загрузить, посмотреть, убрать.

Скрин отчёта Ahrefs или экрана видимости в ИИ специалист снимает по ссылке из
брифа и загружает сюда (команда агентства 07.10.2026: полуавтомат, робот в
интерфейсе Ahrefs — риск блокировки учётки). Загрузка и удаление — под тем же
правом, что бриф (`edit_briefs`): скрины — его часть.

Тело — сырые байты картинки, как у файла списка: multipart ради одного поля
был бы зависимостью без пользы. Предел — 2,5 МБ: прокси сервиса пропускает 3 МБ,
и больший скрин экран ужимает до отправки. Тяжёлая работа — распаковка и
перекодирование — идёт в потоке, а не в цикле событий.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select

from ahrefs_cases import config
from ahrefs_cases.api.body import read_body
from ahrefs_cases.api.deps import SessionDep, UserDep, require_right
from ahrefs_cases.storage import screenshots as files
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.screenshot import KIND_LABELS, SCREENSHOT_KINDS, ProjectScreenshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["screenshots"])

MAX_SCREEN_BYTES = 2_621_440
MAX_PER_PROJECT = 30
"""Больше на один бриф не нужно: три отчёта по стране и экраны ИИ."""

EditDep = Annotated[object, Depends(require_right("edit_briefs"))]
ReadDep = Depends(require_right("read"))


class ScreenshotView(BaseModel):
    id: int
    project_id: int
    kind: str
    caption: str
    mime: str
    width: int
    height: int
    size_bytes: int
    created_at: datetime


class ScreenshotKindView(BaseModel):
    key: str
    label: str


class ScreenshotRules(BaseModel):
    """Что экрану карточки знать до загрузки: виды словами и пределы."""

    kinds: list[ScreenshotKindView]
    max_bytes: int
    max_count: int
    max_side: int
    """Длинная сторона, до которой ужимает сервер: экран ужимает большой снимок до неё же."""


@router.get("/screenshot-rules", response_model=ScreenshotRules, dependencies=[ReadDep])
async def screenshot_rules() -> ScreenshotRules:
    """Экран ужимает и отказывает по пределам сервера, а не по своей копии чисел."""
    return ScreenshotRules(
        kinds=[ScreenshotKindView(key=key, label=KIND_LABELS[key]) for key in SCREENSHOT_KINDS],
        max_bytes=MAX_SCREEN_BYTES,
        max_count=MAX_PER_PROJECT,
        max_side=files.MAX_SIDE,
    )


def _view(row: ProjectScreenshot) -> ScreenshotView:
    return ScreenshotView(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        caption=row.caption,
        mime=row.mime,
        width=row.width,
        height=row.height,
        size_bytes=row.size_bytes,
        created_at=row.created_at,
    )


@router.get(
    "/projects/{project_id}/screenshots",
    response_model=list[ScreenshotView],  # unbounded-ok: у проекта не больше MAX_PER_PROJECT
    dependencies=[ReadDep],
)
async def list_screenshots(project_id: int, session: SessionDep) -> list[ScreenshotView]:
    stmt = (
        select(ProjectScreenshot)
        .where(ProjectScreenshot.project_id == project_id)
        .order_by(ProjectScreenshot.id)
        .limit(MAX_PER_PROJECT)
    )
    return [_view(row) for row in (await session.execute(stmt)).scalars()]


@router.post(
    "/projects/{project_id}/screenshots",
    response_model=ScreenshotView,
    status_code=status.HTTP_201_CREATED,
)
async def upload_screenshot(
    project_id: int,
    request: Request,
    session: SessionDep,
    user: UserDep,
    kind: Annotated[Literal["ahrefs", "ai"], Query()] = "ahrefs",
    caption: Annotated[str, Query(max_length=300)] = "",
    _: EditDep = None,
) -> ScreenshotView:
    """Принять картинку: проверить, ужать, положить на диск, записать строку."""
    if await session.get(Project, project_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"проекта {project_id} нет")
    taken = await session.scalar(
        select(func.count()).where(ProjectScreenshot.project_id == project_id)
    )
    if (taken or 0) >= MAX_PER_PROJECT:
        detail = f"у проекта уже {MAX_PER_PROJECT} скринов — уберите лишние"
        raise HTTPException(status.HTTP_409_CONFLICT, detail=detail)
    raw = await read_body(
        request,
        limit=MAX_SCREEN_BYTES,
        too_large="скрин больше 2,5 МБ — сохраните его в JPEG или уменьшите",
        empty="скрин пуст: в файле нет ни одного байта",
    )
    try:
        prepared = await anyio.to_thread.run_sync(files.prepare, raw)
    except files.ScreenshotRejectedError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    twin = await session.scalar(
        select(ProjectScreenshot.id).where(
            ProjectScreenshot.project_id == project_id,
            ProjectScreenshot.checksum == prepared.checksum,
        )
    )
    if twin is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="этот скрин у проекта уже есть")
    root = config.export.screenshots_dir
    key = await anyio.to_thread.run_sync(files.save, root, project_id, prepared)
    row = ProjectScreenshot(
        project_id=project_id,
        kind=kind,
        caption=caption.strip(),
        storage_key=key,
        mime=prepared.mime,
        width=prepared.width,
        height=prepared.height,
        size_bytes=len(prepared.content),
        checksum=prepared.checksum,
        uploaded_by=user.id,
    )
    session.add(row)
    try:
        await session.commit()
    except Exception:
        # Строка не записалась — файлу без строки на диске не место.
        await anyio.to_thread.run_sync(files.remove, root, key)
        logger.exception("screenshot_not_recorded", extra={"project_id": project_id})
        raise
    logger.info(
        "screenshot_uploaded",
        extra={"project_id": project_id, "screenshot_id": row.id, "bytes": row.size_bytes},
    )
    return _view(row)


@router.get("/screenshots/{screenshot_id}/image", dependencies=[ReadDep])
async def screenshot_image(screenshot_id: int, session: SessionDep) -> Response:
    """Картинка как есть — для карточки; заголовки не дают браузеру гадать тип."""
    row = await _row_or_404(session, screenshot_id)
    try:
        content = await anyio.to_thread.run_sync(
            files.read, config.export.screenshots_dir, row.storage_key
        )
    except FileNotFoundError as exc:
        logger.warning("screenshot_file_missing", extra={"screenshot_id": screenshot_id})
        detail = f"файла скрина {screenshot_id} на диске нет — загрузите его заново"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=detail) from exc
    headers = {
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": "inline",
    }
    return Response(content=content, media_type=row.mime, headers=headers)


@router.delete("/screenshots/{screenshot_id}", response_model=ScreenshotView)
async def delete_screenshot(
    screenshot_id: int, session: SessionDep, _: EditDep = None
) -> ScreenshotView:
    """Убрать скрин: строка — в транзакции, файл — после коммита."""
    row = await _row_or_404(session, screenshot_id)
    view, key = _view(row), row.storage_key
    await session.delete(row)
    await session.commit()
    await anyio.to_thread.run_sync(files.remove, config.export.screenshots_dir, key)
    logger.info("screenshot_deleted", extra={"screenshot_id": screenshot_id})
    return view


async def _row_or_404(session: SessionDep, screenshot_id: int) -> ProjectScreenshot:
    row = await session.get(ProjectScreenshot, screenshot_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"скрина {screenshot_id} нет")
    return row
