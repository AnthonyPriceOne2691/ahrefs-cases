"""Выдача пачки кейсов ZIP-архивом — формат, который называет ТЗ.

У архива две работы. Первая очевидна: отдать десяток PDF одним файлом. Вторая
записана в реестре конфликтов (№7) и легко теряется — **ревью черновика ТЗ не
предусматривает**, поэтому человек, открывающий этот ZIP перед публикацией,
и есть последний предохранитель. Значит, архив обязан помогать смотреть: внутри
лежит список с группой и пометкой «можно публиковать».

Пустой архив не собирается. Пустой ZIP выглядит как поломка выгрузки, а «кейсов
не набралось» — это ответ, и его надо сказать словами (тот же класс, что урок
L1: пустой ответ и недоступный ответ — разные случаи).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ahrefs_cases import config
from ahrefs_cases.cases.model import CaseData
from ahrefs_cases.cases.stoplist import ContentBlockedError
from ahrefs_cases.export.pdf_renderer import filename, render_pdf

MANIFEST_NAME = "кейсы.csv"
MANIFEST_NOTE = "внутренний список: домены всех проектов пачки, клиенту не отдаётся"


class EmptyArchiveError(RuntimeError):
    """Собирать нечего. Не ошибка выгрузки, а её отсутствие — и это разные вещи."""


@dataclass(frozen=True, slots=True)
class PackedCase:
    """Кейс, попавший в архив: файл на диске и имя внутри архива."""

    domain: str
    case: CaseData
    path: Path
    arcname: str


@dataclass(frozen=True, slots=True)
class SkippedCase:
    """Кейс, не попавший в архив, и почему именно."""

    domain: str
    reason: str


@dataclass(frozen=True, slots=True)
class Packed:
    """Готовый архив: где лежит, что внутри, кто не попал."""

    path: Path
    packed: tuple[PackedCase, ...]
    skipped: tuple[SkippedCase, ...]

    def as_lines(self) -> list[str]:
        lines = [f"архив: {self.path}", f"кейсов внутри: {len(self.packed)}"]
        lines.extend(f"  не попал {item.domain}: {item.reason}" for item in self.skipped)
        return lines


def pack(
    cases: Sequence[tuple[str, CaseData]],
    *,
    output_dir: Path | None = None,
    name: str | None = None,
) -> Packed:
    """Собрать кейсы в один архив. Каждый проходит те же проверки, что поодиночке.

    Архив ничего не обходит: стоп-лист и сверка чисел остаются на месте, и кейс,
    который их не прошёл, в пачку не попадает — с названной причиной.
    """
    target_dir = output_dir or config.export.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    packed: list[PackedCase] = []
    skipped: list[SkippedCase] = []
    used: set[str] = set()
    for domain, case in cases:
        try:
            rendered = render_pdf(case, output_dir=target_dir)
        except ContentBlockedError as exc:
            skipped.append(SkippedCase(domain=domain, reason=str(exc)))
            continue
        packed.append(
            PackedCase(
                domain=domain,
                case=case,
                path=rendered.path,
                arcname=_unique(filename(case), used),
            )
        )

    if not packed:
        message = "кейсов для архива не набралось: собирать нечего"
        raise EmptyArchiveError(message)

    archive_path = target_dir / (name or _default_name())
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as bundle:
        for item in packed:
            bundle.write(item.path, arcname=item.arcname)
        bundle.writestr(MANIFEST_NAME, manifest(packed))
    return Packed(path=archive_path, packed=tuple(packed), skipped=tuple(skipped))


def manifest(packed: Sequence[PackedCase]) -> bytes:
    """Список внутри архива — для человека, который смотрит пачку перед выдачей.

    `utf-8-sig`, точка с запятой: файл открывают в Excel, и без BOM кириллица
    там превращается в кракозябры — список, который не читается, не помогает
    никому.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([MANIFEST_NOTE])
    writer.writerow(["домен", "группа", "файл", "можно публиковать"])
    for item in packed:
        writer.writerow(
            [
                item.domain,
                item.case.group.value,
                item.arcname,
                "нет" if item.case.anonymized else "да",
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def _unique(name: str, used: set[str]) -> str:
    """Имена внутри архива не сталкиваются.

    Два проекта одной ниши дают одинаковое «сайт в нише travel — Кейс.pdf», и
    второй молча затёр бы первого: в ZIP это законно, а пачка стала бы короче
    отчёта.
    """
    candidate, counter = name, 2
    stem, _, suffix = name.rpartition(".")
    while candidate in used:
        candidate = f"{stem} ({counter}).{suffix}"
        counter += 1
    used.add(candidate)
    return candidate


def _default_name() -> str:
    return f"кейсы-{datetime.now(UTC).date().isoformat()}.zip"
