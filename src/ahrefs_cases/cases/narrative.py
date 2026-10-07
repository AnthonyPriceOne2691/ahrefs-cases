"""Текст кейса: предложения по числам и программная сверка этих чисел.

Текст опаснее таблицы. Цифру в колонке читатель сверяет глазами с соседней, а
цифру в предложении — нет; она выглядит как часть фразы. Конституция проекта
требует прямо: **числа в кейсе сверяются с данными программно**, потому что
кейс уходит клиенту, а ревью черновика ТЗ не предусматривает вовсе.

Отсюда устройство модуля: текст собирается **только** через форматтеры, которые
берут значения из структуры кейса, а готовая строка потом проверяется против
тех же значений. Совпадения не случилось — текста нет, а не «почти правильный
текст с одной опечаткой».

Чего здесь нет и не будет до отдельного решения заказчика: утверждений о том,
**какие работы велись**. Мы их не знаем: во входном файле есть объём работ
числом и тип услуги — и только они попадают в предложения. LLM-абзац (Q14)
требует волны В3 контура перед первым вызовом модели.
"""

from __future__ import annotations

import re

from ahrefs_cases.cases.format import number, percent
from ahrefs_cases.cases.model import SUBJECT_LABELS, CaseData, Change
from ahrefs_cases.storage._enums import Metric
from ahrefs_cases.storage.geo import WORLDWIDE, countries

MONTHS_RU = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)
"""Месяцы словами: в дате «01.2025» число месяца попало бы в сверку наравне со
значениями метрик и ослабило бы её — «01» совпало бы с чем угодно."""

_NUMBER_RE = re.compile(r"\d[\d  ]*(?:,\d+)?")


class NumbersMismatchError(ValueError):
    """В тексте оказалось число, которого нет в кейсе."""


def compose(case: CaseData) -> str:
    """Собрать текст кейса и сверить его числа со структурой.

    Сверка стоит здесь, а не у вызывающего: текст, который её не прошёл, не
    должен существовать даже в переменной.
    """
    sentences = [
        _intro(case),
        _result(case),
        _support(case),
        _volume(case),
    ]
    text = " ".join(sentence for sentence in sentences if sentence)
    verify_numbers(text, case)
    return text


def _intro(case: CaseData) -> str:
    start, end = case.period.start, case.period.end
    return (
        f"Проект в нише «{case.niche}», {_where(case)}. "
        f"Период работ — {case.period.months} мес.: "
        f"{MONTHS_RU[start.month - 1]} {start.year} — {MONTHS_RU[end.month - 1]} {end.year}."
    )


def _where(case: CaseData) -> str:
    """Где шли работы. У нескольких стран — по какой из них цифры (`storage.geo`):
    без этого «трафик +40 %» под тремя странами читается как сумма по всем. Ряды,
    купленные не по первой стране, называются оговоркой (Z53): обещать «по первой
    из них» тогда значило бы соврать."""
    count = len(countries(case.geo))
    if case.geo == WORLDWIDE:
        place = "география — весь мир"
    elif count == 0:
        place = "страна не указана"
    elif count == 1:
        place = f"страна — {case.geo_label}"
    else:
        place = f"страны — {case.geo_label}"
        if case.geo_note is None:
            return f"{place}; цифры Ahrefs — по первой из них"
    return place if case.geo_note is None else f"{place}; {case.geo_note}"


def _result(case: CaseData) -> str:
    """Главный результат — по точкам А и Б, а не по последнему месяцу.

    Так текст не спорит с кривой: на графике последний измеренный месяц обычно
    другое число, потому что точка Б — среднее по окну (урок L46).
    """
    main = case.change(Metric.ORG_TRAFFIC.value)
    if main is None:
        return ""
    before, after = number(main.before), number(main.after)
    if not main.grew:
        return f"Органический трафик за период работ: {before} → {after} визитов в месяц."
    if main.pct is None:
        return f"Органический трафик вырос с нуля до {after} визитов в месяц."
    return (
        f"Органический трафик вырос на {percent(main.pct).lstrip('+')}: "
        f"с {before} до {after} визитов в месяц."
    )


def _support(case: CaseData) -> str:
    """Подтверждающие метрики — из подсветки, кроме главной."""
    others = [item for item in case.highlights if item.subject != Metric.ORG_TRAFFIC.value]
    if not others:
        return ""
    listed = ", ".join(f"{item.label} — {_change_words(item)}" for item in others)
    return f"Вместе с ним выросли: {listed}."


def _change_words(change: Change) -> str:
    if change.pct is None:
        return f"с нуля до {number(change.after)}"
    return f"{percent(change.pct)} (было {number(change.before)})"


def _volume(case: CaseData) -> str:
    """Объём работ — единственное, что мы знаем о самих работах."""
    if case.work_volume is None:
        return ""
    return f"Объём работ по проекту — {number(float(case.work_volume))}."


def verify_numbers(text: str, case: CaseData) -> None:
    """Каждое число текста обязано быть числом кейса.

    Проверка несимметрична намеренно: кейс может не назвать какое-то из своих
    чисел (в подсветку попадают не все), но назвать чужое — не может.
    """
    allowed = allowed_numbers(case)
    found = {_normalize(token) for token in _NUMBER_RE.findall(_without_names(text, case))}
    unknown = sorted(found - allowed)
    if unknown:
        message = (
            f"в тексте кейса числа, которых нет в его данных: {', '.join(unknown)}. "
            "Текст собирается только из значений структуры — проверьте форматирование"
        )
        raise NumbersMismatchError(message)


def allowed_numbers(case: CaseData) -> set[str]:
    """Числа кейса в том виде, в каком они попадают в текст.

    Строится из структуры теми же форматтерами, что и сам текст: иначе сверка
    проверяла бы совпадение кода с самим собой.
    """
    pieces = [
        str(case.period.start.year),
        str(case.period.end.year),
        str(case.period.months),
    ]
    for change in case.changes:
        pieces.extend((number(change.before), number(change.after), percent(change.pct)))
    if case.work_volume is not None:
        pieces.append(number(float(case.work_volume)))
    return {_normalize(token) for piece in pieces for token in _NUMBER_RE.findall(piece)}


def _without_names(text: str, case: CaseData) -> str:
    """Убрать из текста имена перед сверкой: названия метрик и нишу из файла.

    В названиях есть цифры: «ключи в топ-10», «ключи в топ-3». Это часть имени,
    а не величина, и без этого шага сверка требовала бы числа 10 и 3 в данных
    кейса — то есть ослабла бы ровно там, где должна быть строгой. Поймано
    первым же прогоном, а не рассуждением.

    Ниша — тот же класс, только приходит из файла: «3D-печать», «B2B», «Web3».
    До 07.10.2026 её цифра читалась числом кейса, сборка текста бросала
    `NumbersMismatchError`, и один такой проект ронял пачку целиком. Ниша
    вырезается **вместе с кавычками**, в которых её ставит `_intro`: совпавшее
    с ней число в остальном тексте сверяется по-прежнему.
    """
    if case.niche:
        text = text.replace(f"«{case.niche}»", "«»")
    for label in SUBJECT_LABELS.values():
        text = text.replace(label, " ")
    return text


def _normalize(token: str) -> str:
    return token.replace(" ", "").replace(" ", "").strip()
