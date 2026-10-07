"""Скрины брифа для сборки кейса: строки из базы, байты с диска.

Читаются там же, где собирается кейс (`builder._attempt`), — через него проходят
все пути сборки, и правило «скрины едут в бриф» не живёт в одной обёртке (урок
L127). Файл, которого нет на диске (бэкап базы новее бэкапа файлов, ручная
уборка) или который не читается картинкой, кейс не роняет, но и не пропадает
молча: в журнал с номером скрина. Битый файл отсеивается здесь, а не в рендере:
рендер на битой картинке обрывает сборку, а сбой одного кейса пока роняет всю
пачку (Z54).
"""

from __future__ import annotations

import logging
from pathlib import Path

import anyio.to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.cases.model import CaseImage
from ahrefs_cases.storage.models.screenshot import ProjectScreenshot
from ahrefs_cases.storage.screenshots import ScreenshotRejectedError, ensure_intact, read

logger = logging.getLogger(__name__)


async def load_screens(session: AsyncSession, project_id: int) -> tuple[CaseImage, ...]:
    """Скрины проекта в порядке загрузки; пропавший или битый файл — пропуск с записью в журнал."""
    stmt = (
        select(ProjectScreenshot)
        .where(ProjectScreenshot.project_id == project_id)
        .order_by(ProjectScreenshot.id)
    )
    folder = config.export.screenshots_dir
    images: list[CaseImage] = []
    for row in (await session.execute(stmt)).scalars():
        where = {"project_id": project_id, "screenshot_id": row.id}
        try:
            content = await anyio.to_thread.run_sync(_intact, folder, row.storage_key, row.mime)
        except FileNotFoundError:
            logger.warning("screenshot_missing_for_case", extra=where)
            continue
        except ScreenshotRejectedError as exc:
            logger.warning("screenshot_damaged_for_case", extra={**where, "reason": str(exc)})
            continue
        images.append(CaseImage(kind=row.kind, caption=row.caption, mime=row.mime, content=content))
    return tuple(images)


def _intact(folder: Path, key: str, mime: str) -> bytes:
    content = read(folder, key)
    ensure_intact(content, mime)
    return content
