"""Домен из входного файла → канонический хост-ключ проекта.

    normalize_domain("https://WWW.Example.com/blog/?a=1") -> "example.com"

Хост-ключ — ключ дедупликации проектов и ключ кэша Ahrefs. Поэтому нормализация
живёт одной функцией: разойдись она по местам, «example.com» из файла и
«www.example.com» из другого отдела стали бы двумя проектами и двумя оплатами
одной и той же истории.

Punycode считаем через кодек stdlib (IDNA 2003). Для наших входов — кириллица,
умляуты — этого достаточно; отличия IDNA 2008 (`ß`, `ς`) в доменах агентства не
встречаются, а отдельная зависимость `idna` объявлялась бы ради двух символов.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

from ahrefs_cases.intake.rejections import RejectReason

_MAX_HOST_LEN = 253
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST_RE = re.compile(rf"^{_LABEL}(?:\.{_LABEL})+$")


@dataclass(frozen=True, slots=True)
class DomainRejected:
    """Домен не нормализуется. Причина — код, потому что её показывают на экране."""

    reason: RejectReason
    detail: str = ""


def normalize_domain(raw: str) -> str | DomainRejected:
    """Канонический хост или причина отказа. Исключений не бросает.

    Отказ здесь — рядовой случай (в списке на 100 доменов их единицы), а не сбой,
    поэтому он возвращается значением: вызывающий складывает его в отчёт и
    продолжает разбор следующей строки.
    """
    value = raw.strip()
    if not value:
        return DomainRejected(RejectReason.EMPTY_DOMAIN)

    host = _host_part(value)
    if not host:
        return DomainRejected(RejectReason.INVALID_DOMAIN, raw)

    if _is_ip(host):
        return DomainRejected(RejectReason.IP_ADDRESS, host)

    ascii_host = _to_ascii(host)
    if ascii_host is None:
        return DomainRejected(RejectReason.INVALID_DOMAIN, raw)

    ascii_host = _drop_www(ascii_host)
    if len(ascii_host) > _MAX_HOST_LEN or not _HOST_RE.match(ascii_host):
        return DomainRejected(RejectReason.INVALID_DOMAIN, raw)

    return ascii_host


def _host_part(value: str) -> str:
    """Схема, креды, путь, порт — всё лишнее срезается здесь.

    `urlsplit` не используем намеренно: без схемы он кладёт весь вход в `path`,
    а со схемой вроде `example.com:8080` считает `example.com` схемой. Оба случая
    в выгрузках встречаются, и обходить их пришлось бы теми же строковыми
    операциями, только через ветвление.
    """
    host = value.split("//", 1)[-1]
    host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.rsplit("@", 1)[-1]
    host = host.split(":", 1)[0]
    return host.strip().strip(".").lower()


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _to_ascii(host: str) -> str | None:
    """IDN → punycode по меткам. `None`, если хост непредставим в ASCII."""
    if host.isascii():
        return host
    labels: list[str] = []
    for label in host.split("."):
        try:
            labels.append(label.encode("idna").decode("ascii"))
        except UnicodeError:
            return None
    return ".".join(labels)


def _drop_www(host: str) -> str:
    """`www.` срезается, только если под ним остаётся настоящий домен.

    Иначе хост `www.com` (домен регистратора, не префикс) превратился бы в `com`
    и прошёл бы дальше как валидный TLD-«проект».
    """
    if host.startswith("www.") and host.count(".") >= 2:
        return host[4:]
    return host
