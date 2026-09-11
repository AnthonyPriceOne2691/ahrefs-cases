"""Контент-запрет: проверка кейса перед выдачей артефакта.

ТЗ запрещает в кейсах любые упоминания России и Беларуси — стран, городов,
инструментов, «любых связанных моментов». Это требование, а не пожелание к
тексту: держаться на аккуратности шаблона оно не может, потому что ниша, тип
услуг и клиент приходят из файла заказчика, а текст будет меняться каждой
поставкой.

**Fail-closed, и это свойство порядка вызовов, а не обработчика ошибок.**
Проверка идёт **до** записи файла, поэтому любой её отказ — сработавшее правило,
исключение, падение — означает отсутствие артефакта, а не артефакт без проверки.
«Проверка не отработала» и «проверка пройдена» выглядят одинаково ровно до
первой публикации запрещённого упоминания (тот же класс, что урок L1: пустой
ответ и недоступный ответ — разные случаи).

**Проверяются и гео, и текст.** Код страны `RU` ловится структурно, но проект
с гео `DE` и нишей «доставка из Москвы» запрещён ровно так же.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ahrefs_cases.cases.model import CaseData

FORBIDDEN_GEO = frozenset({"RU", "BY"})
"""Коды стран из запрета. Сравнение регистронезависимое: во входном файле
встречается и `ru`."""

_STEMS: tuple[str, ...] = (
    "росси",
    "russia",
    "беларус",
    "белорус",
    "belarus",
    "москв",
    "moscow",
    "минск",
    "minsk",
    "петербург",
    "petersburg",
    "яндекс",
    "yandex",
    "сберб",
    "sberbank",
    "рунет",
    "runet",
)
"""Основы слов: ищутся подстрокой, поэтому ловят падежи («в России», «из Москвы»)."""

_WHOLE_WORDS: tuple[str, ...] = ("рф", "рб", "мск", "спб")
"""Аббревиатуры: только целым словом. Подстрокой «рф» нашлась бы в «сёрфинге»,
и кейс блокировался бы за вид спорта."""

_WORD_RE = re.compile(rf"(?u)\b(?:{'|'.join(_WHOLE_WORDS)})\b")


class ContentBlockedError(Exception):
    """Кейс не может быть выдан: сработал контент-запрет или проверка не прошла."""


@dataclass(frozen=True, slots=True)
class Hit:
    """Одно срабатывание: где нашли и на чём."""

    where: str
    matched: str

    def describe(self) -> str:
        return f"{self.where}: «{self.matched}»"


def check(case: CaseData) -> tuple[Hit, ...]:
    """Все срабатывания запрета по кейсу. Пустой кортеж — кейс можно выдавать.

    Возвращает **все** совпадения, а не первое: человеку, который правит
    входной файл, нужен полный список, иначе он будет чинить по одному.
    """
    fields = {
        "гео": case.geo,
        "заголовок": case.title,
        "ниша": case.niche,
        "услуга": case.service,
    }
    hits = [hit for where, value in fields.items() for hit in _scan(where, value)]
    if case.geo.upper() in FORBIDDEN_GEO:
        hits.append(Hit(where="гео", matched=case.geo.upper()))
    return tuple(hits)


def ensure_publishable(case: CaseData) -> None:
    """Пропустить кейс дальше или отказать, назвав причину."""
    hits = check(case)
    if hits:
        reasons = "; ".join(hit.describe() for hit in hits)
        message = f"контент-запрет: {reasons}"
        raise ContentBlockedError(message)


def _scan(where: str, value: str) -> list[Hit]:
    lowered = value.casefold()
    found = [Hit(where=where, matched=stem) for stem in _STEMS if stem in lowered]
    found.extend(Hit(where=where, matched=word) for word in _WORD_RE.findall(lowered))
    return found
