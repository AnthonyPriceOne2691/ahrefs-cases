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
import hashlib
import io
import logging
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from ahrefs_cases import config
from ahrefs_cases.cases.model import CaseData
from ahrefs_cases.cases.stoplist import ContentBlockedError
from ahrefs_cases.export.pdf_renderer import filename, render_pdf, unique_name

logger = logging.getLogger(__name__)

MANIFEST_NAME = "кейсы.csv"
MANIFEST_NOTE = "внутренний список: домены всех проектов пачки, клиенту не отдаётся"


class EmptyArchiveError(RuntimeError):
    """Собирать нечего. Не ошибка выгрузки, а её отсутствие — и это разные вещи."""


@dataclass(frozen=True, slots=True)
class ToPack:
    """Кейс, который просят положить в архив, и чей он.

    Опознаёт кейс номер проекта, а не домен: у двух кампаний одного сайта домен
    один и тот же. Пока пачка принимала пары «домен, кейс», вызывающий мог
    сопоставить исход с проектом только доменом — и у `nordvpn.com` вторая
    кампания затирала первую: один PDF в архиве и чужие числа в строке кейса
    (Z39). Номер проходит через `pack` насквозь и возвращается в каждом исходе.
    """

    project_id: int
    domain: str
    case: CaseData


@dataclass(frozen=True, slots=True)
class PackedCase:
    """Кейс, попавший в архив: чей он, файл на диске и имя внутри архива."""

    project_id: int
    domain: str
    case: CaseData
    """Кейс ровно в том виде, в каком лёг в файл (с номером сборки): строку кейса
    в базе пишут им, и запись с файлом не расходятся."""

    path: Path
    arcname: str


@dataclass(frozen=True, slots=True)
class SkippedCase:
    """Кейс, не попавший в архив: чей он и почему именно."""

    project_id: int
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
    cases: Sequence[ToPack],
    *,
    output_dir: Path | None = None,
    name: str | None = None,
) -> Packed:
    """Собрать кейсы в один архив. Каждый проходит те же проверки, что поодиночке.

    Архив ничего не обходит: стоп-лист и сверка чисел остаются на месте, и кейс,
    который их не прошёл, в пачку не попадает — с названной причиной. Каждый
    вход даёт ровно один исход, и в исходе — номер проекта этого входа.
    """
    target_dir = output_dir or config.export.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    packed: list[PackedCase] = []
    skipped: list[SkippedCase] = []
    used: set[str] = set()
    for wanted in cases:
        try:
            rendered = render_pdf(wanted.case, output_dir=target_dir)
        except ContentBlockedError as exc:
            skipped.append(
                SkippedCase(project_id=wanted.project_id, domain=wanted.domain, reason=str(exc))
            )
            continue
        packed.append(
            PackedCase(
                project_id=wanted.project_id,
                domain=wanted.domain,
                case=wanted.case,
                path=rendered.path,
                arcname=unique_name(filename(wanted.case), used),
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


def _default_name() -> str:
    return f"кейсы-{datetime.now(UTC).date().isoformat()}.zip"


def newest_pack(directory: Path) -> Path | None:
    """Самый свежий архив каталога выгрузки — или `None`, если его там нет.

    Сборка одного дня переписывает архив того же имени, поэтому «свежий» — это
    время файла, а не имя (урок L89). Обращение к диску синхронное: вызывают
    его из потока, иначе медленный том останавливает цикл событий.
    """
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


RUN_PACKS = "runs"
"""Подкаталог копий пачек по прогонам. `newest_pack` смотрит только корень
каталога выгрузки (`glob("*.zip")`), поэтому копия прогона «свежей пачкой»
не становится никогда."""

PackStamp = tuple[Path, int]
"""Свежая пачка и время её записи в наносекундах."""


def pack_stamp(directory: Path) -> PackStamp | None:
    """Отпечаток свежей пачки — чтобы после сборки узнать, собрала ли она свою.

    Путь **и** время, а не имя: сборка того же дня переписывает архив того же
    имени (урок L89), и по одному имени новая пачка неотличима от прежней.
    """
    path = newest_pack(directory)
    if path is None:
        return None
    try:
        return path, path.stat().st_mtime_ns
    except OSError as exc:
        logger.warning("pack_stamp_unreadable", extra={"path": str(path), "error": str(exc)})
        return None


@dataclass(frozen=True, slots=True)
class KeptPack:
    """Копия пачки прогона: путь от каталога выгрузки и сколько в ней кейсов."""

    path: str
    cases: int


def keep_run_pack(directory: Path, run_id: int, before: PackStamp | None) -> KeptPack | None:
    """Отложить копию пачки, собранной прогоном; путь копии — от каталога выгрузки.

    `None` — прогон архива не собрал: свежая пачка та же, что до сборки. Так
    бывает, когда собирать нечего, — и прежний архив остаётся самым свежим;
    приписать его прогону значило бы отдать по его кнопке чужую сборку.

    Копия, а не ссылка на пачку дня: следующая сборка того же дня перепишет
    пачку, а прогон обязан отдавать то, что собрал сам.
    """
    after = pack_stamp(directory)
    if after is None or after == before:
        return None
    source = after[0]
    target = directory / RUN_PACKS / str(run_id) / f"{source.stem}-прогон-{run_id}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    # Число кейсов — рядом с путём: кнопка в журнале говорит, сколько файлов
    # придёт, и «54 проекта» строки сборки перестаёт читаться как «54 кейса».
    with ZipFile(target) as bundle:
        cases = sum(1 for name in bundle.namelist() if name.lower().endswith(".pdf"))
    return KeptPack(path=target.relative_to(directory).as_posix(), cases=cases)


def run_pack_path(directory: Path, kept: str) -> Path | None:
    """Файл копии пачки прогона — или `None`, если его нет или путь ведёт наружу.

    Путь берётся из снимка прогона, и пишет его только `keep_run_pack`. Но
    отдаётся файл по HTTP, поэтому выход за `runs/` отсекается здесь, а не
    доверием к записи.
    """
    base = (directory / RUN_PACKS).resolve()
    path = (directory / kept).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path


def packed_checksums(path: Path) -> frozenset[str] | None:
    """sha256 каждого PDF внутри пачки: артефакт кейса хранит сумму того же файла,
    что лёг в архив, — содержимое опознаёт кейс, имя нет (правило 18а).
    `None` — архив не читается, и сказать о его составе нечего."""
    try:
        with ZipFile(path) as bundle:
            return frozenset(
                hashlib.sha256(bundle.read(item)).hexdigest()
                for item in bundle.infolist()
                if item.filename.lower().endswith(".pdf")
            )
    except (BadZipFile, OSError) as exc:
        logger.warning("pack_unreadable", extra={"path": str(path), "error": str(exc)})
        return None
