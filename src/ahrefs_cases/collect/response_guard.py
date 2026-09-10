"""Проверка формы ответа Ahrefs: неверная догадка обязана падать громко.

Формы ответов и имена полей взяты из документации и до Ф7 не проверялись ни
разу (Z2, Z3 в `docs/FINDINGS.md`). Проблема не в самой догадке — её проверит
живой ключ, — а в том, **как** она ломается.

По умолчанию питоновский `.get(key, default)` превращает неверное имя в
пустоту, а пустота у нас имеет смысл: «у домена нет истории». Значит одна
опечатка в имени ключа дала бы сто доменов, помеченных «нет данных», и
запомненных такими на `AHREFS_EMPTY_RETRY_DAYS` дней. Сервис отчитался бы
успехом, потратив units и не собрав ничего.

Поэтому здесь различаются три вещи, которые по умолчанию сливаются:

1. **ключа нет в ответе** — форма не та, это ошибка, и её надо увидеть сразу;
2. **ключ есть, список пуст** — у домена правда нет истории, штатный случай;
3. **строки есть, но поля другие** — форма частично не та; ловится тем, что
   ни одна метрика не разобралась, хотя строки пришли.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

_MAX_KEYS_IN_ERROR = 12


class AhrefsResponseError(RuntimeError):
    """Ответ Ahrefs не той формы, какую мы ожидали.

    Отдельный тип, а не общий сбой: он означает «наши предположения о API
    неверны», и лечится это правкой спеки endpoint'а, а не повтором запроса.
    """


def require_rows(payload: dict[str, Any], key: str, endpoint: str) -> list[dict[str, Any]]:
    """Список строк по ключу. Нет ключа — ошибка, а не пустая история."""
    if key not in payload:
        keys = ", ".join(sorted(payload)[:_MAX_KEYS_IN_ERROR]) or "(тело пустое)"
        message = (
            f"{endpoint}: в ответе нет ключа {key!r}. Пришли ключи: {keys}. "
            "Это расхождение формы ответа с нашей спекой endpoint'а, а не "
            "отсутствие истории у домена — поправьте `EndpointSpec.list_key`."
        )
        raise AhrefsResponseError(message)

    rows = payload[key]
    if not isinstance(rows, list):
        message = f"{endpoint}: по ключу {key!r} ожидался список, пришло {type(rows).__name__}"
        raise AhrefsResponseError(message)
    return [row for row in rows if isinstance(row, dict)]


def require_int(payload: dict[str, Any], key: str, source: str) -> int:
    """Целое по ключу. Нет ключа — ошибка, а не ноль.

    Для остатка квоты это критично: ноль означает «квоты нет», а fail-closed
    превращает его в «ни один прогон не стартует». Сервис исправно не
    работал бы, и выглядело бы это как исчерпанный лимит у заказчика.
    """
    if key not in payload:
        keys = ", ".join(sorted(payload)[:_MAX_KEYS_IN_ERROR]) or "(тело пустое)"
        message = (
            f"{source}: в ответе нет ключа {key!r}. Пришли ключи: {keys}. "
            "Не путать с нулевым остатком: остаток неизвестен, тратить нельзя."
        )
        raise AhrefsResponseError(message)
    try:
        return int(payload[key])
    except (TypeError, ValueError) as exc:
        message = f"{source}: значение {key!r} не число: {payload[key]!r}"
        raise AhrefsResponseError(message) from exc


def ensure_values_parsed(
    rows: list[dict[str, Any]], parsed_values: int, endpoint: str, fields: tuple[str, ...]
) -> None:
    """Строки пришли, а метрик не разобралось ни одной — значит поля другие.

    Третий случай из докстринга модуля: `list_key` угадан верно, а имена
    полей внутри строки — нет. Без этой проверки серия молча состояла бы из
    точек без значений, и классификация назвала бы проект «нет данных».
    """
    if rows and parsed_values == 0:
        sample = ", ".join(sorted(rows[0])[:_MAX_KEYS_IN_ERROR])
        message = (
            f"{endpoint}: пришло {len(rows)} строк, но ни одно из полей "
            f"{fields} не разобрано. Поля в ответе: {sample}. "
            "Форма строки разошлась со спекой endpoint'а."
        )
        raise AhrefsResponseError(message)


def warn_if_not_monthly(points: list[date], endpoint: str, target: str) -> None:
    """История ожидается помесячной; всё остальное ломает арифметику точек А/Б.

    Не ошибка, а предупреждение: данные пришли, ими можно пользоваться, но
    окна усреднения считают месяцы, и недельная сетка сделает их бессмыслицей
    незаметно. Гипотеза H4 в `docs/FINDINGS.md` — проверяется здесь, а
    подтверждается Ф7.
    """
    off_grid = [point for point in points if point.day != 1]
    if off_grid:
        logger.warning(
            "ahrefs_history_not_monthly",
            extra={
                "endpoint": endpoint,
                "target": target,
                "example": off_grid[0].isoformat(),
                "count": len(off_grid),
            },
        )


def warn_if_shallower_than_asked(
    points: list[date], asked_from: date, endpoint: str, target: str
) -> int:
    """Насколько история короче запрошенной. Возвращает разницу в месяцах.

    Гипотеза H3: тариф Advanced покрывает нужную глубину. Если не покрывает,
    мы просим 24 месяца, получаем меньше и считаем это отсутствием данных у
    домена. Разница логируется и возвращается вызывающему, чтобы попасть в
    журнал прогона, а не только в логи.
    """
    if not points:
        return 0
    first = min(points)
    months = (first.year - asked_from.year) * 12 + (first.month - asked_from.month)
    if months > 1:
        logger.warning(
            "ahrefs_history_shallower_than_asked",
            extra={
                "endpoint": endpoint,
                "target": target,
                "asked_from": asked_from.isoformat(),
                "got_from": first.isoformat(),
                "months_missing": months,
            },
        )
    return max(0, months)
