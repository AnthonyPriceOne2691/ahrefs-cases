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

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from zipfile import ZIP_DEFLATED, ZipFile

import anyio.to_thread
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import MAX_PAGE, CaseRow, PackView
from ahrefs_cases.cases.freshness import case_mismatch
from ahrefs_cases.classify.rulesets import active_ruleset
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.verdict import Verdict

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
    project_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[CaseRow]:
    """Библиотека: по одному свежему кейсу на проект, если не просили иначе.

    Пересборка не затирает прежний кейс, а добавляет следующую версию, и за
    несколько сборок их накапливаются десятки. Отдавая всё подряд, библиотека
    отвечала на вопрос «что когда собиралось», тогда как спрашивают у неё
    другое — **какой файл отправить клиенту**; на сотне доменов первая страница
    вдобавок оказывалась занята версиями двух-трёх проектов.

    История никуда не делась: `all_versions=true` отдаёт её целиком.

    `project_id` сужает библиотеку до одного проекта. Заведён ради карточки
    проекта: без него она спрашивала бы всю библиотеку и искала свой кейс
    перебором — на сотне доменов это страница чужих строк ради одной своей.
    Фильтр стоит рядом с `all_versions`, а не отдельным путём
    `/api/projects/{id}/case`: вопрос тот же самый («какой файл отправить
    клиенту»), и второй ответ на него разошёлся бы с первым.
    """
    stmt = (
        select(Case, Project, CaseArtifact)
        .join(Project, Project.id == Case.project_id)
        .outerjoin(CaseArtifact, CaseArtifact.case_id == Case.id)
        .order_by(Case.created_at.desc(), Case.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if project_id is not None:
        stmt = stmt.where(Case.project_id == project_id)
    if not all_versions:
        # Свежий кейс проекта — с наибольшим номером строки: версии пишутся
        # по возрастанию, и брать максимум времени было бы хуже — две сборки
        # одной секунды дали бы два «свежих» кейса одного проекта.
        newest = select(func.max(Case.id)).group_by(Case.project_id).scalar_subquery()
        stmt = stmt.where(Case.id.in_(newest))
    found = (await session.execute(stmt)).all()
    judged = await _verdicts_behind(session, [case for case, _, _ in found])
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
            **judged(case),
        )
        for case, project, artifact in found
    ]


async def _verdicts_behind(
    session: AsyncSession, cases: Sequence[Case]
) -> Callable[[Case], dict[str, object]]:
    """Чем судили кейс и чем судят проект сегодня.

    Кейс принадлежит вердикту, а экран показывает действующий; между ними
    помещается целый пересчёт. У `allthedifferences.com` карточка говорила
    «плохой, −99,9 %», а кнопка отдавала файл «+69 %», собранный по фикстурным
    рядам ещё до живого прогона — числа чужие, имя проекта своё (Z30).

    Оба вердикта берутся двумя запросами на страницу, а не по одному на кейс:
    библиотека отдаёт до ста строк, и запрос в цикле превратил бы её в сто
    первых.
    """
    if not cases:
        return lambda _: {}
    ruleset = await active_ruleset(session)
    mine = {case.verdict_id for case in cases}
    projects = {case.project_id for case in cases}
    by_id = {
        verdict.id: verdict
        for verdict in (
            await session.execute(select(Verdict).where(Verdict.id.in_(mine)))
        ).scalars()
    }
    # Действующий вердикт проекта — последний по этой версии порогов: пересчёт
    # пишет новую строку, а не правит прежнюю.
    current: dict[int, Verdict] = {}
    for verdict in (
        await session.execute(
            select(Verdict)
            .where(Verdict.project_id.in_(projects), Verdict.ruleset_id == ruleset.id)
            .order_by(Verdict.id)
        )
    ).scalars():
        current[verdict.project_id] = verdict

    def judge(case: Case) -> dict[str, object]:
        mine_verdict = by_id.get(case.verdict_id)
        now = current.get(case.project_id)
        return {
            "case_group": mine_verdict.group.value if mine_verdict else None,
            "current_group": now.group.value if now else None,
            "outdated": case_mismatch(case, now),
        }

    return judge


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


MAX_SELECTION = 100


@router.get("/selection/download")
async def download_selection(
    session: SessionDep,
    ids: Annotated[list[int], Query(min_length=1, max_length=MAX_SELECTION)],
) -> FileResponse:
    """Отдать выбранные кейсы одним архивом.

    Почему архивом, а не пачкой отдельных файлов: браузер разрешает вкладке
    одну загрузку за жест человека, и десять подряд он оборвёт молча — человек
    получит два PDF из десяти и не узнает, каких восьми не хватает.

    Почему собирается на лету, а не берётся из `/pack/download`: пачка — это
    результат ПРОГОНА по текущим вердиктам, у неё свой состав и своё время
    сборки. Выборка — ответ на «отправь клиенту вот эти три»; подменить одно
    другим значило бы отдать не то, что выбрали.

    Маршрут объявлен ДО `/{case_id}/download` намеренно: иначе слово
    `selection` уходит в номер кейса — тем же путём, каким туда уходило `pack`
    (см. `test_pack_word_does_not_become_a_case_id`).
    """
    wanted = list(dict.fromkeys(ids))
    artifacts = (
        await session.execute(
            select(CaseArtifact, Case)
            .join(Case, Case.id == CaseArtifact.case_id)
            .where(CaseArtifact.case_id.in_(wanted))
            .order_by(CaseArtifact.built_at.desc())
        )
    ).all()

    # По одному свежему артефакту на кейс: пересборка добавляет строку, и без
    # этого в архив уехали бы две версии одного кейса под одним именем.
    newest: dict[int, CaseArtifact] = {}
    for artifact, case in artifacts:
        newest.setdefault(case.id, artifact)

    missing = [case_id for case_id in wanted if case_id not in newest]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"у кейсов нет артефактов: {', '.join(str(i) for i in missing)}",
        )

    def _build() -> Path:
        """Архив пишется в каталог выгрузки, а не во временный файл процесса.

        `FileResponse` отдаёт файл ПОСЛЕ возврата обработчика, и временный файл,
        удаляемый по выходу из блока, к этому моменту уже не существует.
        """
        directory = config.export.output_dir
        directory.mkdir(parents=True, exist_ok=True)
        out: Path = directory / "выборка-кейсов.zip"
        with ZipFile(out, "w", ZIP_DEFLATED) as archive:
            for case_id in wanted:
                artifact = newest[case_id]
                path = Path(artifact.path)
                if not path.is_file():
                    raise FileNotFoundError(artifact.filename)
                archive.write(path, arcname=artifact.filename)
        return out

    try:
        archive_path = await anyio.to_thread.run_sync(_build)
    except FileNotFoundError as missing_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"файл кейса не найден на диске: {missing_file}",
        ) from missing_file

    return FileResponse(archive_path, filename=archive_path.name, media_type="application/zip")


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
