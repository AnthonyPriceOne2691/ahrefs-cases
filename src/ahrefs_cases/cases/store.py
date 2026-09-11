"""Запись кейса: строка `Case` с версией и `CaseArtifact` с контрольной суммой.

**Пересборка добавляет версию, а не переписывает прошлую.** ТЗ требует
перегенерации кейсов через полгода-год; если прошлая версия затёрта, сравнивать
новую не с чем, а вопрос «почему полгода назад мы показывали другое число» без
ответа. Тот же принцип, что у вердиктов: прошлые решения обязаны оставаться
объяснимыми.

Контрольная сумма файла отвечает на отдельный вопрос — «пересобрали или
переименовали». Без неё два артефакта с разными именами неотличимы от одного
и того же, скопированного дважды.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.cases.format import number, percent
from ahrefs_cases.cases.model import CaseData
from ahrefs_cases.storage._enums import ArtifactFormat, CaseStatus, ProjectStatus
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.project import Project

_CHUNK = 1 << 16


async def store_case(
    session: AsyncSession, *, project_id: int, verdict_id: int, case: CaseData
) -> Case:
    """Записать кейс новой версией и пометить проект готовым."""
    row = Case(
        project_id=project_id,
        verdict_id=verdict_id,
        version=await next_version(session, project_id),
        anonymized=case.anonymized,
        highlights={"picked": [_highlight_json(item) for item in case.highlights]},
        narrative=case.narrative,
        status=CaseStatus.BUILT,
    )
    session.add(row)
    await session.flush()

    project = await session.get(Project, project_id)
    if project is not None:
        project.status = ProjectStatus.CASE_READY
    return row


async def next_version(session: AsyncSession, project_id: int) -> int:
    """Следующая версия кейса проекта. Первая — единица, а не ноль."""
    current = await session.scalar(
        select(func.max(Case.version)).where(Case.project_id == project_id)
    )
    return int(current or 0) + 1


async def store_artifact(
    session: AsyncSession,
    *,
    case_id: int,
    path: Path,
    fmt: ArtifactFormat = ArtifactFormat.PDF,
) -> CaseArtifact:
    """Записать файл кейса вместе с контрольной суммой его содержимого."""
    row = CaseArtifact(
        case_id=case_id,
        fmt=fmt,
        path=str(path),
        filename=path.name,
        checksum=checksum(path),
        built_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return row


def checksum(path: Path) -> str:
    """SHA-256 файла, читаемый кусками: кейс с графиками — сотни килобайт."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _highlight_json(change: Any) -> dict[str, Any]:
    """Подсветка в JSONB — в том же виде, в каком её показывают.

    Числа кладутся и сырыми, и отформатированными: сырые нужны сравнению версий,
    отформатированные — экрану Ф6, который обязан показать ровно то же, что
    показал PDF.
    """
    return {
        "subject": change.subject,
        "label": change.label,
        "before": change.before,
        "after": change.after,
        "pct": change.pct,
        "shown": f"{number(change.before)} → {number(change.after)} ({percent(change.pct)})",
    }
