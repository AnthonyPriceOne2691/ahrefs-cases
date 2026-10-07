"""Гео проекта: канон, разбор ячейки, страна запроса и подпись словами.

Примеры приёмки поставки `countries-multi-geo`: M1 (одна страна — как раньше),
M2 (несколько через запятую, цифры по первой), M3 (весь мир), M4 (непонятое
отклоняется целиком), M5 (UK — это GB), M10 (канон переживает круг «канон →
ячейка → канон»).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ahrefs_cases.storage.countries import COUNTRY_NAMES
from ahrefs_cases.storage.geo import (
    WORLDWIDE,
    GeoRejected,
    ahrefs_country,
    countries,
    label,
    parse_geo,
)


def test_one_country_reads_as_before() -> None:
    """M1: «de» — тот же канон «DE», что принимался всегда, и цифры по нему."""
    assert parse_geo("de") == "DE"
    assert label("DE") == "Германия (DE)"
    assert ahrefs_country("DE") == "DE"


def test_several_countries_keep_order_and_count_by_the_first() -> None:
    """M2: порядок файла — смысл: первая страна та, по которой Ahrefs считает цифры."""
    canon = parse_geo("de, at;CH")

    assert canon == "DE,AT,CH"
    assert countries(canon) == ("DE", "AT", "CH")
    assert ahrefs_country(canon) == "DE"
    assert label(canon) == "Германия (DE), Австрия (AT), Швейцария (CH)"


def test_duplicates_collapse_and_legacy_codes_still_read() -> None:
    """M2: дубль страны схлопывается; код, принятый до справочника, показан как есть."""
    assert parse_geo("DE, de, AT") == "DE,AT"
    assert label("XZ") == "XZ"
    assert label("") == ""
    assert ahrefs_country("") == ""


@pytest.mark.parametrize("cell", ["Worldwide", "WORLDWIDE", " весь мир ", "Весь мир", "ww"])
def test_worldwide_is_asked_without_a_country(cell: str) -> None:
    """M3: весь мир — запрос к Ahrefs без фильтра страны, словами — «Весь мир»."""
    assert parse_geo(cell) == WORLDWIDE
    assert countries(WORLDWIDE) == ()
    assert ahrefs_country(WORLDWIDE) == ""
    assert label(WORLDWIDE) == "Весь мир"


@pytest.mark.parametrize(
    ("cell", "named"),
    [
        ("XZ", "XZ"),
        ("Германия", "Германия"),
        ("DE, XZ, qq", "XZ, qq"),
        ("RUSSIA", "RUSSIA"),
    ],
)
def test_unknown_code_rejects_the_whole_cell(cell: str, named: str) -> None:
    """M4: непонятый код не выбрасывается молча — отказ называет его и не берёт
    строку: выброшенная «Россия» обошла бы запрет стран."""
    result = parse_geo(cell)

    assert isinstance(result, GeoRejected)
    assert named in result.detail


@pytest.mark.parametrize("cell", ["DE, Worldwide", "worldwide; AT", ",, ;"])
def test_worldwide_with_countries_or_no_codes_is_rejected(cell: str) -> None:
    """M4: «весь мир и Германия» — не значение; разделители без кодов — тоже."""
    assert isinstance(parse_geo(cell), GeoRejected)


def test_more_countries_than_the_column_holds_is_rejected() -> None:
    """M4: девяносто стран не помещаются в колонку — отказ словами, а не падение записи."""
    result = parse_geo(", ".join(sorted(COUNTRY_NAMES)[:90]))

    assert isinstance(result, GeoRejected)
    assert "Worldwide" in result.detail


def test_uk_is_great_britain() -> None:
    """M5: UK — не код ISO, но так пишут чаще, чем GB; смысл однозначен."""
    assert parse_geo("uk, ie") == "GB,IE"
    assert label("GB") == "Великобритания (GB)"


@given(
    st.lists(st.sampled_from(sorted(COUNTRY_NAMES)), min_size=1, max_size=12),
    st.sampled_from([", ", ",", "; ", " ", " / "]),
)
def test_canon_survives_a_round_trip(codes: list[str], separator: str) -> None:
    """M10: ячейка → канон → канон; страны в порядке первого появления, у каждой подпись."""
    canon = parse_geo(separator.join(code.lower() for code in codes))
    unique = tuple(dict.fromkeys(codes))

    assert canon == ",".join(unique)
    assert parse_geo(canon) == canon
    assert countries(canon) == unique
    assert ahrefs_country(canon) == unique[0]
    shown = label(canon)
    assert all(f"{COUNTRY_NAMES[code]} ({code})" in shown for code in unique)
