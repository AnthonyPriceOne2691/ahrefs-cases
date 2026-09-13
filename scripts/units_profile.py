#!/usr/bin/env python3
"""Во что обойдётся прогон: считает модель, а не перо.

«Стоимость запуска на 100 URL» — метрика приёмки, которую заказчик назвал сам,
и от неё зависит боевой лимит, который он закупает. Число это уже дважды
расходилось с кодом: сначала модель «50 units за запрос» занизила смету в
девять раз, потом «10 units за любое поле» завысила цену позиций в семь.
Оба раза документ пересчитывали руками, и оба раза он отставал от кода в тот
же день, когда менялась цена.

Поэтому профиль считается **из тех же спек, по которым пойдёт прогон**
(`collect/endpoints.py`) и тем же правилом выбора схемы (`collect/scheme.py`),
а таблица вставляется в документ генератором:

    python3 scripts/units_profile.py                 # напечатать
    python3 scripts/units_profile.py --write         # вставить в документ

Сверку документа с расчётом держит `tests/test_units_profile.py`: подорожал
endpoint — оракул краснеет, и документ нельзя не обновить.

Ahrefs здесь не спрашивают: расчёт чистый, из цен полей и арифметики окон.
Смета **боевого списка** считается сервисом на экране загрузки — там настоящие
периоды проектов и кэш; этот профиль отвечает на вопрос «сколько просить»,
пока списка ещё нет.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ahrefs_cases.collect.endpoints import (
    DOMAIN_RATING_HISTORY,
    KEYWORDS_GRAPH,
    KEYWORDS_HISTORY,
    METRICS_HISTORY,
    METRICS_VALUE,
    REFDOMAINS_HISTORY,
    EndpointSpec,
)
from ahrefs_cases.collect.scheme import PointWindows, choose_scheme
from ahrefs_cases.config.ahrefs import CollectSchemeMode

_DOC = Path(__file__).resolve().parents[1] / "docs" / "UNITS_OPTIMIZATION.md"
_BEGIN = "<!-- начало таблицы: scripts/units_profile.py --write -->"
_END = "<!-- конец таблицы -->"

_ANCHOR = date(2025, 7, 1)
"""Конец периода в расчёте. Любой: цена зависит от длины окна, а не от даты —
глубина истории (24 месяца) при периоде в 18 не упирается ни в какой край."""

_POINT_WINDOW_MONTHS = 2
"""Окно точки А/Б из `config/thresholds.example.yml` (Приложение А). Меньше
того, что влезает под минимальную стоимость запроса, поэтому на цену не влияет —
но передаётся честно, чтобы профиль считался тем же вызовом, что и прогон."""


@dataclass(frozen=True, slots=True)
class Stage:
    """Ступень прогона: чьи endpoint'ы, скольким проектам и как их зовут."""

    title: str
    specs: tuple[EndpointSpec, ...]
    count: int


@dataclass(frozen=True, slots=True)
class Line:
    """Строка сметы: один endpoint одной ступени."""

    stage: str
    endpoint: str
    scheme: str
    row_units: int
    per_project: int
    count: int

    @property
    def units(self) -> int:
        return self.per_project * self.count


def _cost(spec: EndpointSpec, months: int, stage1_mode: CollectSchemeMode) -> tuple[str, int]:
    """Цена endpoint'а на один проект и выбранная схема.

    Схему выбирает `choose_scheme` — то же правило, что в прогоне. Умножить
    цену строки на месяцы значило бы посчитать другой прогон: у половины
    endpoint'ов дешевле две точки, и разница на сотне доменов — тысячи units.
    """
    choice = choose_scheme(
        spec=spec,
        period_start=_shift(_ANCHOR, -months),
        period_end=_ANCHOR,
        windows=PointWindows(point_months=_POINT_WINDOW_MONTHS),
        max_history_months=24,
        mode=stage1_mode if spec is METRICS_HISTORY else "auto",
    )
    units = sum(spec.estimate_units(window.rows) for window in choice.windows)
    return choice.scheme.value, units


def _shift(anchor: date, months: int) -> date:
    total = anchor.year * 12 + (anchor.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def profile(
    *,
    projects: int,
    candidates: int,
    cases: int,
    months: int,
    stage1_mode: CollectSchemeMode = "history",
) -> list[Line]:
    """Смета прогона по ступеням воронки.

    Шаг 1 идёт историей не по цене, а по решению 11.09.2026: та же покупка даёт
    график, диагностику «плохих» и пересчёт по любым окнам. Шаг 2 и ступень
    кейса выбирают схему по цене — кроме кривой позиций, которой серия нужна по
    назначению (`needs_series`).

    `stage1_mode="auto"` считает второй маршрут — «точки везде». Он дешевле, и
    именно поэтому его цена нужна рядом: разница и есть то, что мы платим за
    график, диагностику Ф3в и пересчёт окон при калибровке.
    """
    stages = (
        Stage("шаг 1, все проекты", (METRICS_HISTORY,), projects),
        Stage("шаг 2, кандидаты", (KEYWORDS_HISTORY, REFDOMAINS_HISTORY), candidates),
        Stage(
            "ступень кейса",
            (DOMAIN_RATING_HISTORY, KEYWORDS_GRAPH, METRICS_VALUE),
            cases,
        ),
    )
    lines = []
    for stage in stages:
        for spec in stage.specs:
            scheme, per_project = _cost(spec, months, stage1_mode)
            lines.append(
                Line(
                    stage=stage.title,
                    endpoint=spec.name,
                    scheme="серия (по назначению)" if spec.needs_series else scheme,
                    row_units=spec.row_units(),
                    per_project=per_project,
                    count=stage.count,
                )
            )
    return lines


def _spaced(value: int) -> str:
    """Число с неразрывными пробелами по тысячам: его читает человек, а не diff."""
    return f"{value:,}".replace(",", "\u00a0")


def render(lines: list[Line], *, projects: int, months: int) -> str:
    """Таблица для документа. Числа те же, что вернул расчёт, без округлений."""
    total = sum(line.units for line in lines)
    head = [
        f"Профиль ТЗ: {projects} доменов, период работ {months} месяцев "
        f"({months + 1} строк — обе границы включительно).",
        "",
        "| Ступень | Endpoint | Схема | Строка | На проект | Проектов | Units |",
        "|---|---|---|---|---|---|---|",
    ]
    body = [
        f"| {line.stage} | `{line.endpoint}` | {line.scheme} | {line.row_units} | "
        f"{line.per_project} | {line.count} | {line.units} |"
        for line in lines
    ]
    tail = [
        f"| **Итого** | | | | | | **{total}** |",
        "",
        f"**{_spaced(total)} units на прогон, {round(total / projects)} на домен.**",
    ]
    return "\n".join(head + body + tail)


def write(document: Path, table: str) -> bool:
    """Вставить таблицу между маркерами. `False` — маркеров нет."""
    text = document.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(_BEGIN) + r".*?" + re.escape(_END),
        re.DOTALL,
    )
    if not pattern.search(text):
        return False
    document.write_text(pattern.sub(f"{_BEGIN}\n{table}\n{_END}", text, count=1), encoding="utf-8")
    return True


def table_in(document: Path) -> str | None:
    """Что сейчас записано между маркерами. `None` — маркеров нет."""
    found = re.search(
        re.escape(_BEGIN) + r"\n(.*?)\n" + re.escape(_END),
        document.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    return found.group(1) if found else None


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", type=int, default=100, help="доменов в прогоне")
    parser.add_argument("--candidates", type=int, default=30, help="кандидатов после шага 1")
    parser.add_argument("--cases", type=int, default=10, help="проектов, которым соберут кейс")
    parser.add_argument("--months", type=int, default=18, help="длительность работ, месяцев")
    parser.add_argument(
        "--stage1",
        choices=("history", "auto"),
        default="history",
        help="схема шага 1: history — принятый маршрут, auto — «точки везде» для сравнения",
    )
    parser.add_argument("--write", action="store_true", help=f"вставить таблицу в {_DOC.name}")
    args = parser.parse_args()

    lines = profile(
        projects=args.projects,
        candidates=args.candidates,
        cases=args.cases,
        months=args.months,
        stage1_mode=args.stage1,
    )
    table = render(lines, projects=args.projects, months=args.months)
    print(table)
    if args.write:
        if args.stage1 != "history":
            print("\n--write пишет принятый маршрут: повтори без --stage1", file=sys.stderr)
            return 1
        if not write(_DOC, table):
            print(f"\nв {_DOC} нет маркеров {_BEGIN} и {_END}", file=sys.stderr)
            return 1
        print(f"\nтаблица записана в {_DOC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
