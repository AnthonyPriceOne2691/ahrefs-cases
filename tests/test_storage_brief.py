"""Бриф копирайтеру: описание полей шаблона и разбор значения.

Примеры приёмки поставки `brief-fields-api`: M14 (каталог по шаблону), M15 (пункт
списка ключом и подписью), M16 (ссылка только на Google Drive), M17 (текст:
края, предел, «очистить»).
"""

from __future__ import annotations

import pytest

from ahrefs_cases.storage.brief import (
    FIELDS,
    FIELDS_BY_KEY,
    SECTIONS,
    BriefRejected,
    FieldKind,
    label_of,
    normalize,
)


def test_catalog_follows_the_template() -> None:
    """M14: пять разделов в порядке шаблона, ключи уникальны, у списков есть пункты."""
    assert SECTIONS == (
        "Инфо о сотруднике",
        "Проект",
        "Анализ данных",
        "Выполненные работы",
        "Результаты работы",
    )
    assert len(FIELDS_BY_KEY) == len(FIELDS)
    assert {field.section for field in FIELDS} == set(SECTIONS)
    for field in FIELDS:
        keys = [choice.key for choice in field.choices]
        assert (field.kind is FieldKind.CHOICE) == bool(keys), field.key
        assert len(keys) == len(set(keys)), field.key
    columns = [field.column for field in FIELDS if field.column]
    assert columns == [
        "topic",
        "site_type",
        "client_request",
        "complexity",
        "complexity_note",
        "folder_url",
    ]


@pytest.mark.parametrize(
    ("key", "raw", "stored"),
    [
        ("site_type", "marketplace", "marketplace"),
        ("site_type", "  МАРКЕТПЛЕЙС ", "marketplace"),
        ("complexity", "Очень высокая", "very_high"),
        ("topic", "путешествия", "travel"),
    ],
)
def test_choice_is_known_by_key_and_by_label(key: str, raw: str, stored: str) -> None:
    """M15: в файле пункт пишут словами, API присылает ключ — хранится ключ."""
    field = FIELDS_BY_KEY[key]

    assert normalize(field, raw) == stored
    assert label_of(field, stored) != stored


def test_foreign_choice_is_refused_with_the_list() -> None:
    """M15: чужой пункт не записывается молча, отказ перечисляет допустимые."""
    result = normalize(FIELDS_BY_KEY["complexity"], "адская")

    assert isinstance(result, BriefRejected)
    assert "«адская»" in result.detail
    assert "Очень высокая" in result.detail


@pytest.mark.parametrize(
    "raw",
    [
        "https://drive.google.com/drive/folders/abc",
        "https://docs.google.com/document/d/xyz/edit",
    ],
)
def test_drive_link_is_kept(raw: str) -> None:
    """M16: ссылка на папку или документ Google Drive проходит как есть."""
    assert normalize(FIELDS_BY_KEY["folder_url"], raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        "http://drive.google.com/drive/folders/abc",
        "javascript:alert(1)",
        "https://drive.google.com.evil.example/folders/abc",
        "https://yadi.sk/d/abc",
        "папка у Пети",
    ],
)
def test_other_links_are_refused(raw: str) -> None:
    """M16: на листе копирайтера — только https на Google Drive, не ссылка куда угодно."""
    assert isinstance(normalize(FIELDS_BY_KEY["folder_url"], raw), BriefRejected)


def test_text_is_trimmed_bounded_and_clearable() -> None:
    """M17: края срезаются, длинное — отказ, пустое — «очистить»."""
    field = FIELDS_BY_KEY["client_request"]

    assert normalize(field, "  рост заявок из органики  ") == "рост заявок из органики"
    assert normalize(field, "   ") == ""
    assert isinstance(normalize(field, "я" * (field.max_len + 1)), BriefRejected)
