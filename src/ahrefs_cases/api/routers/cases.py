"""Библиотека кейсов, скачивание файла и выдача пачки.

Файл лежит на диске, в базе — путь и контрольная сумма. Поэтому «кейс есть» и
«файл есть» это два разных вопроса, и ответ на второй бывает отрицательным:
каталог выгрузки переносят и чистят. Пустой ответ с кодом 200 в этом случае
неотличим от «кейса нет» — отдаём `404` (тот же класс, что урок L1).

Пачка ZIP — выход сервиса по ТЗ, и до этой поставки забрать её можно было
только с диска сервера. У пачки нет своей строки в базе: она собирается
прогоном и переписывается следующей сборкой того же дня. Поэтому свежая
пачка ищется по каталогу выгрузки — это единственное место, где она есть.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from ahrefs_cases import config
from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import MAX_PAGE, CaseRow, PackView
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
    all_versions: bool = False,
) -> list[CaseRow]:
    """Библиотека: по одному свежему кейсу на проект, если не просили иначе.

    Пересборка не затирает прежний кейс, а добавляет следующую версию, и за
    несколько сборок их накапливаются десятки. Отдавая всё подряд, библиотека
    отвечала на вопрос «что когда собиралось», тогда как спрашивают у неё
    другое — **какой файл отправить клиенту**; на сотне доменов первая страница
    вдобавок оказывалась занята версиями двух-трёх проектов.

    История никуда не делась: `all_versions=true` отдаёт её целиком.
    """
    stmt = (
        select(Case, Project, CaseArtifact)
        .join(Project, Project.id == Case.project_id)
        .outerjoin(CaseArtifact, CaseArtifact.case_id == Case.id)
        .order_by(Case.created_at.desc(), Case.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if not all_versions:
        # Свежий кейс проекта — с наибольшим номером строки: версии пишутся
        # по возрастанию, и брать максимум времени было бы хуже — две сборки
        # одной секунды дали бы два «свежих» кейса одного проекта.
        newest = select(func.max(Case.id)).group_by(Case.project_id).scalar_subquery()
        stmt = stmt.where(Case.id.in_(newest))
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


def _newest_pack() -> Path | None:
    """Самый свежий архив каталога выгрузки — или `None`, если его там нет.

    Сборка одного дня переписывает архив того же имени, поэтому «свежий» — это
    время файла, а не имя. Обращение к диску синхронное нарочно: вызывают его
    из потока, иначе медленный том останавливает цикл событий.
    """
    directory = config.export.output_dir
    if not directory.is_dir():
        return None
    dated: list[tuple[float, Path]] = []
    for path in directory.glob("*.zip"):
        try:
            dated.append((path.stat().st_mtime, path))
        except OSError:
            # Файл исчез между перечислением и опросом: пачку пересобирают
            # прямо сейчас. Это не отказ выдачи — остальные архивы на месте,
            # и правильный ответ здесь «пропустить», а не «упасть».
            continue
    if not dated:
        return None
    return max(dated)[1]


@router.get("/pack", response_model=PackView)
async def pack_state() -> PackView:
    """Что за пачка лежит и когда собрана.

    Объявлен **выше** `/{case_id}/download`: ниже слово `pack` уехало бы в
    целочисленный параметр и превратило выдачу в `422` — та же ловушка, что
    поймала смету прогона.
    """
    path = await anyio.to_thread.run_sync(_newest_pack)
    if path is None:
        return PackView(
            exists=False,
            note="пачка ещё не собиралась: соберите кейсы, и архив появится здесь",
        )
    stat = await anyio.to_thread.run_sync(path.stat)
    return PackView(
        exists=True,
        filename=path.name,
        size_bytes=stat.st_size,
        built_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        note="архив собран последней сборкой кейсов",
    )


@router.get("/pack/download")
async def download_pack() -> FileResponse:
    """Отдать пачку целиком — тем же файлом, что лежит в каталоге выгрузки."""
    path = await anyio.to_thread.run_sync(_newest_pack)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="пачки кейсов нет: она собирается прогоном сборки кейсов",
        )
    return FileResponse(path, filename=path.name, media_type="application/zip")


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
