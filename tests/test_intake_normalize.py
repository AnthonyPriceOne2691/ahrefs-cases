"""Нормализация домена: golden-таблица «вход → канонический хост».

Пример приёмки: B4. Таблица, а не набор функций: дедупликация проектов и ключ
кэша Ahrefs стоят на этой функции, и список случаев здесь должен читаться
целиком, чтобы новый случай добавлялся строкой.
"""

from __future__ import annotations

import pytest

from ahrefs_cases.intake.normalize import DomainRejected, normalize_domain
from ahrefs_cases.intake.rejections import RejectReason

ACCEPTED = [
    ("example.com", "example.com"),
    ("HTTPS://WWW.Example.com/path?utm=1", "example.com"),
    ("http://пример.рф", "xn--e1afmkfd.xn--p1ai"),
    ("example.com.", "example.com"),
    ("  example.com  ", "example.com"),
    ("http://example.com:8080/", "example.com"),
    ("user:pw@sub.example.co.uk:8443/x", "sub.example.co.uk"),
    ("shop.example.net/shop/", "shop.example.net"),
    ("EXAMPLE.COM", "example.com"),
    ("//example.com", "example.com"),
    ("ftp://example.com/pub", "example.com"),
    ("www.com", "www.com"),
    ("münchen.de", "xn--mnchen-3ya.de"),
    ("example.com/#anchor", "example.com"),
]

REJECTED = [
    ("", RejectReason.EMPTY_DOMAIN),
    ("   ", RejectReason.EMPTY_DOMAIN),
    ("не домен", RejectReason.INVALID_DOMAIN),
    ("localhost", RejectReason.INVALID_DOMAIN),
    ("example", RejectReason.INVALID_DOMAIN),
    ("under_score.com", RejectReason.INVALID_DOMAIN),
    ("-leading.example.com", RejectReason.INVALID_DOMAIN),
    ("https://", RejectReason.INVALID_DOMAIN),
    ("1.2.3.4", RejectReason.IP_ADDRESS),
    ("http://192.168.0.1/admin", RejectReason.IP_ADDRESS),
    ("2001:db8::1", RejectReason.INVALID_DOMAIN),
]


@pytest.mark.parametrize(("raw", "expected"), ACCEPTED)
def test_normalize_accepts(raw: str, expected: str) -> None:
    """B4: вход приводится к каноническому хосту."""
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(("raw", "reason"), REJECTED)
def test_normalize_rejects(raw: str, reason: RejectReason) -> None:
    """B4: негодный вход отклоняется с кодом причины, а не исключением."""
    result = normalize_domain(raw)

    assert isinstance(result, DomainRejected)
    assert result.reason == reason


def test_www_and_bare_collapse_to_one_key() -> None:
    """Смысл нормализации: два написания одного домена — один ключ.

    Это не стилистика, а деньги: разойдись ключи, историю одного домена купили бы
    дважды — по разу на каждый отдел, заказавший его в своём списке.
    """
    assert normalize_domain("https://www.example.com/") == normalize_domain("EXAMPLE.COM")


def test_table_can_fail() -> None:
    """Проверка проверки: функция действительно приводит вход, а не отдаёт его как есть.

    Без этого теста реализация `return raw.strip().lower()` прошла бы половину
    таблицы, и её зелёный цвет ничего бы не значил.
    """
    assert (
        normalize_domain("HTTPS://WWW.Example.com/path?utm=1")
        != "https://www.example.com/path?utm=1"
    )
