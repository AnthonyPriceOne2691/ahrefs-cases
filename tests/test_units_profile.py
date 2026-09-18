"""Цена прогона: документ обязан совпадать с моделью.

Число «сколько стоит прогон по ТЗ» — метрика приёмки, названная заказчиком, и
от неё зависит боевой лимит, который он закупает. Оно уже дважды расходилось с
кодом: «50 units за запрос» занизила смету в девять раз, «10 units за любое
поле» завысила цену позиций в семь. Оба раза документ правили пером, и оба раза
он отставал в тот же день, когда менялась цена.

Оракул закрывает именно это: таблица в `docs/UNITS_OPTIMIZATION.md` собирается
генератором, и тест сверяет её с тем, что модель считает **сейчас**. Ahrefs
здесь не участвует — расчёт чистый, из цен полей и арифметики окон.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import MappingProxyType, ModuleType

import pytest

from ahrefs_cases.collect import endpoints
from ahrefs_cases.collect.endpoints import KEYWORDS_HISTORY

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "units_profile.py"
_DOC = Path(__file__).resolve().parents[1] / "docs" / "UNITS_OPTIMIZATION.md"

_TZ_PROFILE = {"projects": 100, "candidates": 30, "cases": 10, "months": 18}


def _module() -> ModuleType:
    """Скрипт не пакет: импортируется по пути, как его запускает человек.

    `sys.modules` заполняется до `exec_module` не для красоты: `@dataclass`
    ищет собственный модуль по имени и падает `AttributeError` на пустой
    записи — поймано этим же тестом при первом запуске.
    """
    spec = importlib.util.spec_from_file_location("units_profile", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


units_profile = _module()


def _total(**profile: int) -> int:
    return sum(line.units for line in units_profile.profile(**profile))


def test_the_run_by_the_sheet_costs_what_we_tell_the_customer() -> None:
    """E1: профиль ТЗ — 28 970 units, 290 на домен.

    Число зафиксировано здесь, потому что его называют заказчику: боевой лимит
    от 35 000 просят под него. Сдвинулось — значит поменялась цена или схема, и
    разговор с заказчиком надо повторить, а не молча переписать документ.
    """
    total = _total(**_TZ_PROFILE)

    assert total == 28_970
    assert round(total / _TZ_PROFILE["projects"]) == 290


def test_documents_carry_the_number_the_model_computes() -> None:
    """E2: таблица в документе совпадает с расчётом посимвольно.

    Если не совпало — не правь тест: запусти
    `python3 scripts/units_profile.py --write` и перечитай текст вокруг
    таблицы, числа в нём тоже могли устареть.
    """
    lines = units_profile.profile(**_TZ_PROFILE)
    expected = units_profile.render(
        lines, projects=_TZ_PROFILE["projects"], months=_TZ_PROFILE["months"]
    )

    assert units_profile.table_in(_DOC) == expected


def test_a_pricier_endpoint_turns_the_oracle_red(monkeypatch: pytest.MonkeyPatch) -> None:
    """E3: подорожание endpoint'а обязано ломать сверку.

    Оракул, который не краснеет на изменении, охраняет только собственное
    существование. Дорожает здесь `org_traffic` — поле шага 1, то есть цена
    всех ста доменов. Правится таблица цен, а не спека: спека заморожена
    (`frozen=True`), и это правильно — цена endpoint'а не должна меняться в
    рантайме.
    """
    monkeypatch.setattr(
        endpoints, "FIELD_PRICES", MappingProxyType({**endpoints.FIELD_PRICES, "org_traffic": 20})
    )

    assert _total(**_TZ_PROFILE) != 28_970


def test_short_period_is_bought_whole_and_long_one_by_points() -> None:
    """E4: схему выбирает цена, а не константа в профиле.

    Шесть месяцев историей — 77 units против 100 точками, и график достаётся
    даром; восемнадцать — наоборот. Профиль обязан звать то же правило, что
    прогон, иначе он считает другой прогон.
    """
    short = {name: value for name, value in _TZ_PROFILE.items() if name != "months"} | {"months": 6}

    keywords_short = next(
        line
        for line in units_profile.profile(**short, stage1_mode="auto")
        if line.endpoint == KEYWORDS_HISTORY.name
    )
    keywords_long = next(
        line
        for line in units_profile.profile(**_TZ_PROFILE, stage1_mode="auto")
        if line.endpoint == KEYWORDS_HISTORY.name
    )

    assert keywords_short.scheme == "full_history"
    assert keywords_long.scheme == "two_points"


def test_points_everywhere_is_the_cheaper_route_and_we_know_its_price() -> None:
    """Второй маршрут посчитан той же моделью: разница и есть цена решения.

    «Точки везде» дешевле на 10 900 units — ровно на шаге 1, по 109 на домен.
    Это не аргумент против принятого маршрута, а его цена, названная числом:
    за неё куплены график, диагностика Ф3в и пересчёт окон при калибровке.
    """
    accepted = _total(**_TZ_PROFILE)
    points_everywhere = _total(**_TZ_PROFILE, stage1_mode="auto")

    assert accepted - points_everywhere == 10_900
