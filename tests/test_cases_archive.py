"""Нейминг по ТЗ и выдача пачки ZIP-архивом.

Примеры приёмки поставки `case-zip`: E1–E3 (имена), E4 (состав архива), E5
(список внутри), E6 (контент-запрет), E8 (совпадающие имена), E9 (пересборка),
E10 (пустая пачка). E7 (проекты без кейса) закрыт исходами сборки в поставке
`case-structure`: в пачку приходят только собранные кейсы.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

from ahrefs_cases.cases.model import CaseData, Change, Period
from ahrefs_cases.classify.deltas import Delta
from ahrefs_cases.export.archive import MANIFEST_NAME, EmptyArchiveError, pack
from ahrefs_cases.export.pdf_renderer import filename
from ahrefs_cases.storage._enums import Group


def _case(**overrides: object) -> CaseData:
    change = Change(
        subject="org_traffic",
        delta=Delta(before=1000.0, after=2400.0, absolute=1400.0, pct=140.0),
    )
    fields: dict[str, object] = {
        "title": "example.com",
        "anonymized": False,
        "geo": "US",
        "niche": "fintech",
        "service": "seo",
        "period": Period(start=date(2025, 1, 1), end=date(2026, 1, 1)),
        "work_volume": None,
        "group": Group.GOOD,
        "ruleset_version": "2026-09-A",
        "changes": (change,),
    }
    fields.update(overrides)
    return CaseData(**fields)  # type: ignore[arg-type]


def test_public_case_is_named_by_the_site() -> None:
    """E1: «название сайта + Кейс» — правило ТЗ дословно."""
    assert filename(_case()) == "example.com — Кейс.pdf"


def test_anonymous_case_is_named_by_the_niche() -> None:
    """E2: домена в имени файла нет — его нет и в самом кейсе."""
    name = filename(_case(title="сайт в нише travel", anonymized=True, niche="travel"))

    assert name == "сайт в нише travel — Кейс.pdf"
    assert "example" not in name


def test_unsafe_characters_are_cleaned() -> None:
    """E3: раздел сайта в заголовке не должен создавать подкаталоги."""
    name = filename(_case(title="shop.example.net/раздел?x=1"))

    assert "/" not in name and "?" not in name
    assert name.endswith(" — Кейс.pdf")


def test_archive_holds_cases_and_the_list(tmp_path: Path) -> None:
    """E4 и E5: три PDF и список, по которому пачку смотрят перед публикацией."""
    cases = [
        ("example.com", _case()),
        ("example.org", _case(title="сайт в нише travel", anonymized=True, niche="travel")),
    ]

    bundle = pack(cases, output_dir=tmp_path)

    with ZipFile(bundle.path) as archive:
        names = archive.namelist()
        manifest = archive.read(MANIFEST_NAME).decode("utf-8-sig")
    assert "example.com — Кейс.pdf" in names
    assert "сайт в нише travel — Кейс.pdf" in names
    assert MANIFEST_NAME in names
    assert "example.org;good;сайт в нише travel — Кейс.pdf;нет" in manifest
    assert "example.com;good;example.com — Кейс.pdf;да" in manifest


def test_blocked_case_stays_out_and_says_why(tmp_path: Path) -> None:
    """E6: запрещённый кейс не попадает в пачку, и молчания об этом нет."""
    cases = [("example.com", _case()), ("forbidden.example", _case(geo="RU"))]

    bundle = pack(cases, output_dir=tmp_path)

    assert [item.domain for item in bundle.skipped] == ["forbidden.example"]
    assert "контент-запрет" in bundle.skipped[0].reason
    with ZipFile(bundle.path) as archive:
        assert len(archive.namelist()) == 2  # один кейс и список


def test_identical_titles_do_not_collide(tmp_path: Path) -> None:
    """E8: два проекта одной ниши дают одно имя, и второй затёр бы первого."""
    anonymous = _case(title="сайт в нише travel", anonymized=True, niche="travel")
    bundle = pack(
        [("a.example", anonymous), ("b.example", replace(anonymous))], output_dir=tmp_path
    )

    arcnames = [item.arcname for item in bundle.packed]
    assert arcnames == ["сайт в нише travel — Кейс.pdf", "сайт в нише travel — Кейс (2).pdf"]
    with ZipFile(bundle.path) as archive:
        assert len(archive.namelist()) == 3


def test_second_pack_rebuilds_the_archive(tmp_path: Path) -> None:
    """E9: архив — снимок пачки, а не журнал: повтор пересобирает его целиком."""
    cases = [("example.com", _case())]

    first = pack(cases, output_dir=tmp_path, name="кейсы.zip")
    second = pack(cases, output_dir=tmp_path, name="кейсы.zip")

    assert first.path == second.path
    with ZipFile(second.path) as archive:
        assert len(archive.namelist()) == 2


def test_empty_batch_makes_no_archive(tmp_path: Path) -> None:
    """E10: пустой ZIP читается как поломка выгрузки, а не как «кейсов нет»."""
    with pytest.raises(EmptyArchiveError):
        pack([], output_dir=tmp_path)

    assert not list(tmp_path.glob("*.zip"))
