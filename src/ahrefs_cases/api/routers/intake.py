"""Приём списка проектов по HTTP: файл или ссылка на Google Sheet.

До этого роутера список попадал в сервис только командой `run_collect.py
intake`. Загружают его PR-отдел и руководители — люди без консоли и без доступа
к серверу, и «ручной запуск» из ТЗ означал для них «позвать инженера».

**Файл принимается телом запроса**, имя — параметром. Multipart потребовал бы
новой зависимости (`python-multipart`) ради одного-единственного поля, а
браузер умеет слать `File` телом без всякой обвязки. Станет полей несколько —
зависимость вернётся осознанно.

Разбор при этом тот же, что у консольного приёма (`intake.read_upload`): у
одного файла не должно быть двух правд о том, какие строки годны.

**Два брака — два ответа.** Брак строк — отчёт `200`: годные строки приняты,
битые названы номером и причиной. Брак файла (нет колонок, одна шапка, книга
не читается) — отказ `400` целиком, и ни строки не записано: отчёт «принято 0»
над таким файлом выглядел успешным приёмом.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api.deps import SessionDep, require_right
from ahrefs_cases.api.schemas import IntakeLink, IntakeReportView, RejectionRow
from ahrefs_cases.intake.accept import UnknownSourceError, accept, read_upload
from ahrefs_cases.intake.gsheet_source import SheetAccessError, SheetLinkError, read_gsheet
from ahrefs_cases.intake.rejections import Notice, Rejection, UnfitSourceError
from ahrefs_cases.intake.report import IntakeReport
from ahrefs_cases.intake.rows import RawTable

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/intake",
    tags=["intake"],
    dependencies=[Depends(require_right("run"))],
)

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
"""Предел размера тела. ТЗ ограничивает вход сотней проектов, а не байтами:
сотня строк — это килобайты, и книга на два мегабайта уже означает, что прислали
не то (отчёт с картинками, выгрузку целиком). Предел назван в тексте отказа,
чтобы человек знал, во что упёрся."""


@router.post("/file", response_model=IntakeReportView)
async def intake_file(
    session: SessionDep,
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
) -> IntakeReportView:
    """Принять список из файла: XLSX или CSV телом запроса."""
    data = await _read_body(request)
    try:
        return await _accept(session, read_upload(filename, data))
    except UnknownSourceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnfitSourceError as exc:
        raise _unfit(f"Файл «{filename}»", exc) from exc


@router.post("/link", response_model=IntakeReportView)
async def intake_link(session: SessionDep, link: IntakeLink) -> IntakeReportView:
    """Принять список из опубликованной Google Sheet.

    Таблица проверяется целиком так же, как файл: путь тот же (`_accept`), и
    отказ тот же — отличается только подлежащее.
    """
    try:
        return await _accept(session, read_gsheet(link.url))
    except (SheetLinkError, SheetAccessError) as exc:
        # Закрытая таблица отвечает **страницей входа со статусом 200** (L10).
        # Читатель это различает; роутер обязан донести причину как отказ, а не
        # показать «принято 0» — иначе человек пойдёт чинить свой файл. Это
        # своя причина — «откройте доступ», — и она не смешивается с «не подходит».
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnfitSourceError as exc:
        raise _unfit("Таблица по ссылке", exc) from exc


def _unfit(subject: str, exc: UnfitSourceError) -> HTTPException:
    """Брак файла: отказ целиком, база не тронута. Кто прислал — говорит вызывающий.

    Отказ пишется в лог полем, а не текстом: по нему видно, сколько списков не
    доходит до приёма и почему, — без этого прод молчит о них так же, как
    раньше молчал ответ «принято 0».
    """
    logger.info("intake_refused", extra={"subject": subject, "reason": str(exc)})
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"{subject} не подходит: {exc}")


async def _read_body(request: Request) -> bytes:
    """Тело запроса с проверкой предела **по ходу чтения**.

    Считать `Content-Length` недостаточно: заголовок присылает клиент, и
    доверять ему значит принять тело любого размера от того, кто соврал. Поток
    обрывается на пределе, то есть лишние байты в память не попадают.
    """
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    f"файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ. "
                    "Ожидается список проектов (до 100 строк), а не выгрузка целиком."
                ),
            )
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="файл пуст: в нём нет ни одного байта. Выберите файл со списком.",
        )
    return body


async def _accept(session: AsyncSession, table: RawTable) -> IntakeReportView:
    """Проверить таблицу, записать годные строки и ответить отчётом."""
    report = await accept(session, table)
    await session.commit()
    logger.info(
        "intake_accepted",
        extra={
            "origin": report.origin,
            "accepted": report.accepted,
            "rejected_rows": report.rejected_rows,
        },
    )
    return _view(report)


def _rows(items: Iterable[Rejection | Notice]) -> list[RejectionRow]:
    """Отказы и замечания показываются одинаково: разные у них последствия, а
    не форма. Номер строки — тот, который человек ищет глазами в Excel."""
    return [
        RejectionRow(
            row_no=item.row_no,
            field=item.field,
            reason=item.reason.value,
            detail=item.detail,
        )
        for item in sorted(items, key=lambda item: (item.row_no, item.field))
    ]


def _view(report: IntakeReport) -> IntakeReportView:
    return IntakeReportView(
        origin=report.origin,
        accepted=report.accepted,
        created=report.created,
        updated=report.updated,
        rejected_rows=report.rejected_rows,
        by_reason={reason.value: count for reason, count in report.by_reason().items()},
        rejections=_rows(report.rejections),
        notices=_rows(report.notices),
        project_ids=list(report.project_ids),
    )
