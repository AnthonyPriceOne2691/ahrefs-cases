"""Гео проекта: одна страна, несколько или весь мир — как хранится и как читается.

    parse_geo("de, at,CH")   -> "DE,AT,CH"
    parse_geo("Worldwide")   -> "WW"
    ahrefs_country("DE,AT,CH") -> "DE"
    label("DE,AT,CH")        -> "Германия (DE), Австрия (AT), Швейцария (CH)"

Колонка `projects.geo` хранит канон: коды ISO 3166-1 alpha-2 заглавными через
запятую, в порядке файла, или `WORLDWIDE`. Порядок — смысл, а не случайность:
цифры кейса Ahrefs считает по **первой** стране списка (решение владельца
07.10.2026). Главную страну выбирает тот, кто пишет файл, — ставит её первой;
остальные идут в шапку и в текст кейса. Сумма по странам стоила бы units на
каждую страну, «весь мир» для мультигео смешал бы целевые рынки с остальными.

Модуль лежит в хранилище, потому что формат колонки нужен слоям, которые друг
друга не видят: приёму (проверить ячейку), сбору (спросить Ahrefs), кейсу и
экрану (назвать страну словами).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from ahrefs_cases.storage.countries import COUNTRY_NAMES

WORLDWIDE = "WW"
"""Весь мир: запрос к Ahrefs без фильтра страны. `WW` не присвоен ни одной
стране ISO 3166-1, поэтому с кодом страны не спутается."""

WORLDWIDE_LABEL = "Весь мир"

GEO_MAX_LEN = 255
"""Ширина колонки `projects.geo`: 85 стран в одной ячейке."""

_WORLDWIDE_WORDS = frozenset({"worldwide", "весь мир", "ww"})
_ALIASES = {"UK": "GB"}
"""`UK` — не код ISO, но Великобританию так пишут чаще, чем `GB`, и смысл однозначен."""

_SEPARATORS = re.compile(r"[,;/\s]+")
"""Через запятую просила команда; точка с запятой, косая черта и пробел — то,
что в той же ячейке Excel пишут руками, и смысл у них тот же."""


@dataclass(frozen=True, slots=True)
class GeoRejected:
    """Ячейка гео не разобрана. `detail` — что именно, словами для отчёта о приёме."""

    detail: str


def parse_geo(raw: str) -> str | GeoRejected:
    """Значение ячейки → канон или причина отказа. Исключений не бросает.

    Отказ — **весь**, а не по непонятому коду: гео — вход запрета стран
    (`cases.stoplist`), и строка, у которой выбросили `Россия` и оставили `DE`,
    прошла бы мимо него. Пустую ячейку здесь не разбирают — её ловит
    обязательность колонки.
    """
    value = raw.strip()
    if value.casefold() in _WORLDWIDE_WORDS:
        return WORLDWIDE
    tokens = [token for token in _SEPARATORS.split(value) if token]
    if not tokens:
        return GeoRejected("нет ни одного кода страны")
    if any(token.casefold() in _WORLDWIDE_WORDS for token in tokens):
        return GeoRejected(f"«{value}»: Worldwide пишется один, без стран")
    unknown = [token for token in tokens if _code(token) not in COUNTRY_NAMES]
    if unknown:
        return GeoRejected(f"не код страны: {', '.join(unknown)}")
    canon = ",".join(dict.fromkeys(_code(token) for token in tokens))
    if len(canon) > GEO_MAX_LEN:
        return GeoRejected(f"больше {GEO_MAX_LEN // 3} стран — для всего мира пишут Worldwide")
    return canon


def countries(geo: str) -> tuple[str, ...]:
    """Канон → коды стран в порядке файла. У «всего мира» стран нет."""
    if not geo or geo == WORLDWIDE:
        return ()
    return tuple(geo.split(","))


def ahrefs_country(geo: str) -> str:
    """Страна запроса к Ahrefs: первая из списка; весь мир — пусто, то есть без фильтра."""
    codes = countries(geo)
    return codes[0] if codes else ""


def label(geo: str) -> str:
    """Гео словами: «Германия (DE)», через запятую по странам, «Весь мир».

    Код, которого нет в справочнике, показывается как есть: проект, принятый
    до проверки по справочнику, назвать некрасиво, уронить кейс — хуже.
    """
    if geo == WORLDWIDE:
        return WORLDWIDE_LABEL
    return ", ".join(_name(code) for code in countries(geo))


def rows_note(geo: str, bought: Collection[str]) -> str | None:
    """Оговорка, когда купленные ряды — не по первой стране проекта; `None` — всё по ней.

    Сбор считает окна купленными и после смены первой страны цифры не перекупает: ряд
    остаётся по прежней стране или смешивается с новыми месяцами (Z53). Решение
    владельца 07.10.2026 — не докупать, а предупреждать. Текст один на карточку и
    лист брифа: два экземпляра разошлись бы при первой правке.

    `bought` — страны купленных точек проекта (`metric_points.country`, пусто — весь мир).
    """
    wanted = ahrefs_country(geo)
    others = sorted(set(bought) - {wanted})
    if not others:
        return None
    lead = "часть цифр Ahrefs куплена" if wanted in bought else "цифры Ahrefs куплены"
    now = (
        f"первой страной проекта стала {_name(wanted)}" if wanted else "проект перевели на весь мир"
    )
    return f"{lead} {_bought_where(others)} — до того, как {now}"


def _bought_where(codes: Sequence[str]) -> str:
    named = [_name(code) for code in codes if code]
    places = (
        [("по стране " if len(named) == 1 else "по странам ") + ", ".join(named)] if named else []
    )
    if "" in codes:
        places.append("по всему миру")
    return " и ".join(places)


def _code(token: str) -> str:
    upper = token.upper()
    return _ALIASES.get(upper, upper)


def _name(code: str) -> str:
    name = COUNTRY_NAMES.get(code.upper())
    return f"{name} ({code.upper()})" if name else code
