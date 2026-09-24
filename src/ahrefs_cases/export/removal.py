"""Что удаление проекта уносит с собой: строки, файлы кейсов и отдачу пачки.

Строки уносит каскад схемы (`ON DELETE CASCADE`: точки, вердикты всех версий,
кейсы, артефакты). Здесь — два вопроса, которых каскад не решает: какие PDF
уходят с диска и можно ли после этого отдавать пачку ZIP. Журналы не
трогаются: у строки прогона ссылка становится `NULL`, домен и расход остаются,
а журнал расхода — единственный след оплаты (урок L202).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.export.archive import packed_checksums
from ahrefs_cases.storage.models import Case, CaseArtifact, MetricPoint, Project, RunItem, Verdict

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProjectTrace:
    """След проекта до удаления: строки по таблицам и файлы его кейсов."""

    metric_points: int
    verdicts: int
    cases: int
    run_items: int
    twin_campaigns: int
    artifacts: tuple[tuple[str, str], ...]
    """Путь и sha256 каждого артефакта его кейсов."""


async def trace_of(session: AsyncSession, project: Project) -> ProjectTrace:
    """Что тянется за проектом. Вторая кампания сайта — не его: у неё свои копии
    месяцев (`cache.share_twin_points`), и они остаются."""

    async def count(*where: Any) -> int:
        return int(await session.scalar(select(func.count()).where(*where)) or 0)

    artifacts = await session.execute(
        select(CaseArtifact.path, CaseArtifact.checksum)
        .join(Case, Case.id == CaseArtifact.case_id)
        .where(Case.project_id == project.id)
    )
    return ProjectTrace(
        metric_points=await count(MetricPoint.project_id == project.id),
        verdicts=await count(Verdict.project_id == project.id),
        cases=await count(Case.project_id == project.id),
        run_items=await count(RunItem.project_id == project.id),
        twin_campaigns=await count(
            Project.domain == project.domain,
            Project.target_mode == project.target_mode,
            Project.id != project.id,
        ),
        artifacts=tuple((path, checksum) for path, checksum in artifacts.all()),
    )


async def delete_rows(session: AsyncSession, project: Project) -> None:
    """Одним оператором — остальное уносит каскад. Явный порядок «от детей»
    обязан помнить `cases → verdicts` (`RESTRICT`) — вторая копия схемы."""
    await session.execute(delete(Project).where(Project.id == project.id))


async def own_files(
    session: AsyncSession, project_id: int, trace: ProjectTrace, output_dir: Path
) -> list[Path]:
    """PDF проекта, которые можно стереть: из каталога выгрузки и ничьи больше.

    Файл бывает общим — одинаковый кейс не дублируется на диске
    (`pdf_renderer._same_content`), пачка пишет одну ссылку двум кейсам (Z39).
    """
    names = {Path(path).name for path, _ in trace.artifacts}
    if not names:
        return []
    others = await session.execute(
        select(CaseArtifact.path)
        .join(Case, Case.id == CaseArtifact.case_id)
        .where(CaseArtifact.filename.in_(names), Case.project_id != project_id)
    )
    return await asyncio.to_thread(
        _unshared, [path for path, _ in trace.artifacts], list(others.scalars()), output_dir
    )


def _unshared(paths: Sequence[str], others: Sequence[str], output_dir: Path) -> list[Path]:
    """Сверка по разрешённому пути: `data/out/x.pdf` и `/app/data/out/x.pdf` — один
    файл. Относительный путь — от рабочего каталога, как у скачивания кейса."""
    root = output_dir.resolve()
    taken = {Path(path).resolve() for path in others}
    own: list[Path] = []
    for raw in dict.fromkeys(paths):
        path = Path(raw).resolve()
        if not path.is_relative_to(root):
            logger.info("project_file_outside_output", extra={"path": raw})
            continue
        if path not in taken and path.is_file():
            own.append(path)
    return own


def remove_files(paths: Sequence[Path]) -> int:
    """Стереть файлы — **после** коммита: откат не оставит кейсов без файлов.
    Не стёрся — в лог с путём: строки уже ушли, файл без строки — мусор."""
    removed = 0
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("project_file_not_removed", extra={"path": str(path), "error": str(exc)})
            continue
        removed += 1
    return removed


async def holds_deleted_case(
    session: AsyncSession, pack: Path, *, without: int | None = None
) -> bool:
    """Есть ли в пачке PDF, чьей sha256 нет ни у одного артефакта, — кейс
    удалённого проекта. Имя кейс не опознаёт, содержимое — да (правило 18а).

    `without` — спросить так, будто этого проекта уже нет. Нечитаемый архив —
    «не знаю», и он отдаётся, как раньше.
    """
    sums = await asyncio.to_thread(packed_checksums, pack)
    if not sums:
        return False
    stmt = (
        select(CaseArtifact.checksum)
        .join(Case, Case.id == CaseArtifact.case_id)
        .where(CaseArtifact.checksum.in_(sums))
    )
    if without is not None:
        stmt = stmt.where(Case.project_id != without)
    return bool(sums - set((await session.execute(stmt)).scalars()))
