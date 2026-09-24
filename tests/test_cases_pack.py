"""Пачка кейсов: у каждой кампании свой кейс, свой файл и своя строка списка.

Примеры приёмки поставки `two-campaigns-two-cases` (Z39): W1 (два файла в
архиве), W2 (у каждой кампании свои числа и свой файл), W3 (номер сборки —
своей кампании), W4 («(2)» — у поздней кампании), W5 (контент-запрет одной
кампании не отнимает кейс у другой). W6 — исполнение на копии дев-базы.

Проверяется `pack_cases` — его зовут и команда `pack`, и задача очереди за
кнопкой «Собрать кейсы». Он ходит своими соединениями, поэтому тест пишет свои
строки с коммитом, берёт свою версию порогов и убирает за собой: откат тестовой
транзакции записей приложения не видит (уроки L68, L79, Z12).
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import select
from tests.owned_rows import delete_owned, isolated_ruleset

from ahrefs_cases.cli.case_commands import EXIT_CONTENT_BLOCKED, pack_cases
from ahrefs_cases.storage._enums import CaseStatus, Group, Metric, MetricSource
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict

DOMAIN = "two-campaigns.example"
RULESET = "тест-две-кампании"
"""Своя версия порогов: `pack_cases` собирает кейсы по действующей версии, и по
чужой тест собрал бы пачку из проектов стенда."""

Write = Callable[[Callable[..., object]], None]


@dataclass(frozen=True, slots=True)
class Campaign:
    """Кампания сайта: календарный год работ и трафик на границах периода."""

    year: int
    before: float
    after: float
    group: Group
    geo: str = "US"
    earlier_builds: int = 0
    """Сколько раз кейс кампании уже собирали: следующий номер сборки на единицу
    больше."""

    @property
    def start(self) -> date:
        return date(self.year, 1, 1)

    @property
    def end(self) -> date:
        return date(self.year, 12, 1)


FIRST = Campaign(year=2025, before=1000.0, after=2000.0, group=Group.GOOD)
SECOND = Campaign(year=2026, before=3000.0, after=3600.0, group=Group.MEDIUM)


@pytest.fixture(scope="module")
def writer() -> Iterator[Write]:
    """Один цикл и движок на модуль — запись мимо приложения (уроки L51, L54)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from ahrefs_cases import config

    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Callable[..., object]) -> None:
        async def _apply() -> None:
            async with AsyncSession(engine) as session:
                await action(session)
                await session.commit()

        loop.run_until_complete(_apply())

    try:
        yield run
    finally:
        loop.run_until_complete(engine.dispose())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


def _cleanup(write: Write) -> None:
    async def _delete(session: object) -> None:
        await delete_owned(session, domains=(DOMAIN,))  # type: ignore[arg-type]

    write(_delete)


@pytest.fixture
def own_rows(migrated_db: None, writer: Write) -> Iterator[None]:
    """Свои проекты и своя действующая версия порогов; после теста — ничего своего."""
    _cleanup(writer)
    undo = isolated_ruleset(writer, RULESET)
    yield
    undo()
    _cleanup(writer)


@pytest.fixture
def out_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Каталог выгрузки теста: пачка и PDF не ложатся в каталог стенда."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    return tmp_path


def _point(at: date, traffic: float) -> dict[str, object]:
    """Точка вердикта в том виде, в каком её пишет `classify/verdicts.store`."""
    return {
        "at": at.isoformat(),
        "months_used": 2,
        "values": {"org_traffic": traffic},
        "derived": {},
    }


def _seed(write: Write, *campaigns: Campaign) -> None:
    """Кампании одного сайта: проект, вердикт своей версии порогов и ряд трафика.

    Ряд постоянен в каждой половине года — точки вердикта воспроизводятся по нему
    при окнах версии теста (два месяца), и сверка чисел кейс не остановит.
    Порядок записи — порядок аргументов: W4 заводит позднюю кампанию первой.
    """

    async def _write(session: object) -> None:
        ruleset_id = await session.scalar(  # type: ignore[attr-defined]
            select(Ruleset.id).where(Ruleset.version == RULESET)
        )
        for campaign in campaigns:
            project = Project(
                domain=DOMAIN,
                period_start=campaign.start,
                period_end=campaign.end,
                niche="fintech",
                geo=campaign.geo,
                service_type="seo",
                client="Acme",
                owner="i.petrov",
                publishable=True,
                notes="",
            )
            session.add(project)  # type: ignore[attr-defined]
            await session.flush()  # type: ignore[attr-defined]
            verdict = Verdict(
                project_id=project.id,
                ruleset_id=ruleset_id,
                group=campaign.group,
                score=0.0,
                reasons={},
                point_a=_point(campaign.start, campaign.before),
                point_b=_point(campaign.end, campaign.after),
                source=MetricSource.FIXTURE,
            )
            session.add(verdict)  # type: ignore[attr-defined]
            await session.flush()  # type: ignore[attr-defined]
            session.add_all(  # type: ignore[attr-defined]
                [
                    MetricPoint(
                        project_id=project.id,
                        metric=Metric.ORG_TRAFFIC,
                        point_date=date(campaign.year, month, 1),
                        value=campaign.before if month <= 6 else campaign.after,
                        source=MetricSource.FIXTURE,
                        fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
                    )
                    for month in range(1, 13)
                ]
            )
            session.add_all(  # type: ignore[attr-defined]
                [
                    Case(
                        project_id=project.id,
                        verdict_id=verdict.id,
                        version=version,
                        anonymized=False,
                        highlights={},
                        status=CaseStatus.BUILT,
                    )
                    for version in range(1, campaign.earlier_builds + 1)
                ]
            )

    write(_write)


@dataclass(frozen=True, slots=True)
class Stored:
    """Свежая строка `cases` кампании и её артефакт — как они лежат в базе."""

    period_start: date
    version: int
    shown: str
    filename: str
    checksum: str


def _stored(write: Write) -> dict[int, Stored]:
    """Последняя сборка каждой кампании сайта теста: год → строка кейса."""
    found: dict[int, Stored] = {}

    async def _read(session: object) -> None:
        rows = (
            await session.execute(  # type: ignore[attr-defined]
                select(Project.period_start, Case, CaseArtifact)
                .join(Case, Case.project_id == Project.id)
                .join(CaseArtifact, CaseArtifact.case_id == Case.id)
                .where(Project.domain == DOMAIN)
                .order_by(Case.id)
            )
        ).all()
        for start, case, artifact in rows:
            picked = case.highlights.get("picked") or [{}]
            found[start.year] = Stored(
                period_start=start,
                version=case.version,
                # Разряды кейс делит неразрывным пробелом (`cases.format`); здесь
                # обычный, чтобы ожидание читалось глазами.
                shown=str(picked[0].get("shown", "")).replace(" ", " "),
                filename=artifact.filename,
                checksum=artifact.checksum,
            )

    write(_read)
    return found


def _pack() -> int:
    return asyncio.run(pack_cases(MetricSource.FIXTURE))


def _archive(out: Path) -> tuple[dict[str, str], list[list[str]]]:
    """PDF сайта теста в свежей пачке (имя → sha256) и строки списка про него."""
    newest = max(out.glob("*.zip"), key=lambda path: path.stat().st_mtime)
    with ZipFile(newest) as bundle:
        pdfs = {
            name: hashlib.sha256(bundle.read(name)).hexdigest()
            for name in bundle.namelist()
            if name.startswith(DOMAIN) and name.endswith(".pdf")
        }
        listed = bundle.read("кейсы.csv").decode("utf-8-sig")
    rows = [row for row in csv.reader(io.StringIO(listed), delimiter=";") if row[0] == DOMAIN]
    return pdfs, rows


def test_two_campaigns_get_two_files(own_rows: None, writer: Write, out_dir: Path) -> None:
    """W1: две хорошие кампании одного сайта — два PDF и две строки списка.

    Ключом пачки был домен: вторая кампания затирала первую, и в архив уходил
    один PDF на двоих — на стенде так у `nordvpn.com` во всех сборках.
    """
    _seed(writer, FIRST, SECOND)

    assert _pack() == 0

    pdfs, rows = _archive(out_dir)
    assert sorted(pdfs) == [
        f"{DOMAIN} — Кейс v1 (2).pdf",
        f"{DOMAIN} — Кейс v1.pdf",
    ], "у каждой кампании свой файл"
    assert len(set(pdfs.values())) == 2, "два разных файла, а не копия одного"
    assert sorted((row[1], row[2]) for row in rows) == [
        ("good", f"{DOMAIN} — Кейс v1.pdf"),
        ("medium", f"{DOMAIN} — Кейс v1 (2).pdf"),
    ]


def test_each_campaign_keeps_its_numbers_and_file(
    own_rows: None, writer: Write, out_dir: Path
) -> None:
    """W2: строка `cases` каждой кампании — её числа и её файл из архива.

    Прежде обе строки писались кейсом одной кампании и ссылались на один файл:
    подсветка «6 894 → 10 840» у обеих кампаний `nordvpn.com`.
    """
    _seed(writer, FIRST, SECOND)

    _pack()

    pdfs, _ = _archive(out_dir)
    stored = _stored(writer)
    assert sorted(stored) == [2025, 2026], "строка кейса у каждой кампании"
    assert stored[2025].shown.startswith("1 000 → 2 000")
    assert stored[2026].shown.startswith("3 000 → 3 600")
    assert stored[2025].filename != stored[2026].filename
    for year, row in stored.items():
        assert pdfs[row.filename] == row.checksum, f"артефакт кампании {year} — её файл в архиве"


def test_build_number_is_the_campaigns_own(own_rows: None, writer: Write, out_dir: Path) -> None:
    """W3: номер сборки в имени файла — своей кампании и равен версии её строки."""
    _seed(writer, Campaign(2025, 1000.0, 2000.0, Group.GOOD, earlier_builds=3), SECOND)

    _pack()

    pdfs, _ = _archive(out_dir)
    assert sorted(pdfs) == [f"{DOMAIN} — Кейс v1.pdf", f"{DOMAIN} — Кейс v4.pdf"]
    stored = _stored(writer)
    assert (stored[2025].version, stored[2025].filename) == (4, f"{DOMAIN} — Кейс v4.pdf")
    assert (stored[2026].version, stored[2026].filename) == (1, f"{DOMAIN} — Кейс v1.pdf")


def test_earlier_campaign_gets_the_plain_name(own_rows: None, writer: Write, out_dir: Path) -> None:
    """W4: «(2)» — у поздней кампании, какой бы строкой её ни завели и сколько бы
    раз ни собирали.

    Порядок двух кампаний решал порядок строк Postgres при равных доменах, и он
    плавает: у `nordvpn.com` «выживала» то одна кампания, то другая.
    """
    _seed(writer, SECOND, FIRST)

    for build in (1, 2):
        _pack()
        stored = _stored(writer)
        assert stored[2025].filename == f"{DOMAIN} — Кейс v{build}.pdf"
        assert stored[2026].filename == f"{DOMAIN} — Кейс v{build} (2).pdf"


def test_blocked_campaign_does_not_take_the_other_away(
    own_rows: None, writer: Write, out_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """W5: запрет одной кампании не снимает с пачки другую и не даёт ей чужой файл."""
    _seed(writer, FIRST, Campaign(2026, 3000.0, 3600.0, Group.MEDIUM, geo="BY"))

    assert _pack() == EXIT_CONTENT_BLOCKED

    pdfs, rows = _archive(out_dir)
    assert list(pdfs) == [f"{DOMAIN} — Кейс v1.pdf"]
    assert [(row[1], row[2]) for row in rows] == [("good", f"{DOMAIN} — Кейс v1.pdf")]
    stored = _stored(writer)
    assert sorted(stored) == [2025], "запрещённая кампания строки кейса не получает"
    assert pdfs[stored[2025].filename] == stored[2025].checksum
    assert f"не попал {DOMAIN}: контент-запрет: гео: «BY»" in capsys.readouterr().out
