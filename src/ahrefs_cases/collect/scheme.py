"""Схема сбора: покупать историю целиком или две точки на границах периода.

Чистая арифметика по замеренной цене Ahrefs. Ни базы, ни провайдера, ни
`date.today()`: решение зависит только от периода работ, окон точек и модели
стоимости, поэтому его можно проверить таблицей примеров, а не прогоном.

Почему выбор, а не одна схема на всех. Цена запроса — `max(50, строки × цена
строки)`, и минимум делает короткие проекты дешевле собрать целиком: семь строк
стоят 77 против 100 за две точки, и график достаётся даром. Длинные — наоборот:
девятнадцать строк стоят 209 против тех же 100. Разница на сотне доменов
достигает десяти тысяч units **в обе стороны**, поэтому схема считается на
каждый проект.

Окна точек приходят **параметром**, а не чтением активной версии порогов:
контракт `layers` в `.importlinter` запрещает `collect` знать про `classify`
(классификация обязана быть бесплатной и переигрываемой на уже собранных
данных). Кто просит окно, тот его и передаёт — `scripts/run_collect.py`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.config.ahrefs import CollectSchemeMode


class CollectScheme(StrEnum):
    """Способ покупки истории одного проекта."""

    FULL_HISTORY = "full_history"
    TWO_POINTS = "two_points"


@dataclass(frozen=True, slots=True)
class PointWindows:
    """Сколько месяцев просят пороги. Ноль означает «не задано» — берём минимум.

    `point_months` — окно усреднения точки из версии порогов
    (`windows.point_a_months` / `point_b_months`, максимум из двух). Мы всё
    равно покупаем не меньше, чем влезает под минимальную стоимость запроса,
    поэтому «не задано» — не дыра в данных, а честное «купим бесплатный
    максимум». Если калибровка поднимет окно выше этого максимума, число
    обязано приехать сюда, иначе точка будет считаться по месяцам, которых мы
    не купили — это видно в `Point.months_used`, но лучше не создавать случай.

    `baseline_months` — сколько месяцев брать ДО старта работ: сумма
    `windows.pre_start_baseline_months` (опция ТЗ «рост начался после старта»,
    по умолчанию выключена) и `AHREFS_HISTORY_LEAD_MONTHS`.
    """

    point_months: int = 0
    baseline_months: int = 0


@dataclass(frozen=True, slots=True)
class Window:
    """Окно запроса: обе границы включительно, по одной строке на месяц."""

    date_from: date
    date_to: date

    def __post_init__(self) -> None:
        """Перевёрнутое окно — ошибка, а не запрос «на одну строку».

        Поймано тестом E13: упор в `max_history_months` сдвигал начало окна
        точки А вперёд, а конец оставлял на месте, и получалось окно с
        `date_to` раньше `date_from`. `rows` возвращал единицу, планировщик
        ставил задачу, Ahrefs получил бы бессмысленный интервал — 50 units за
        пустой ответ, который выглядит как «у домена нет истории». Инвариант
        стоит здесь, потому что построить такое окно нельзя вообще, а не только
        в схеме точек.
        """
        if self.date_to < self.date_from:
            message = (
                f"окно запроса перевёрнуто: date_from={self.date_from}, "
                f"date_to={self.date_to} — так бывает при упоре в глубину истории, "
                "и это ошибка расчёта границ, а не свойство проекта"
            )
            raise ValueError(message)

    @property
    def rows(self) -> int:
        """Строк в ответе. **На одну больше, чем месяцев между границами.**

        Обе границы входят в ответ, поэтому период 18 месяцев — это 19 строк.
        Из-за этой единицы точка безразличия между схемами стоит на восьми
        месяцах, а не на девяти: 99 units против 100.
        """
        months = (self.date_to.year - self.date_from.year) * 12 + (
            self.date_to.month - self.date_from.month
        )
        return max(1, months + 1)


@dataclass(frozen=True, slots=True)
class SchemeChoice:
    """Что решено по одному проекту — и во что обошлись бы оба варианта.

    Цены обоих вариантов возвращаются **всегда**, а не только выбранного: смета
    без отвергнутой цены выглядит произвольной («почему два похожих проекта
    стоят по-разному?»), а экран загрузки Ф6 обязан объяснять выбор оператору
    до запуска. Заказчик подтвердил это требование 10.09.2026.
    """

    scheme: CollectScheme
    windows: tuple[Window, ...]
    units_full_history: int
    units_two_points: int
    reason: str

    @property
    def units(self) -> int:
        """Цена выбранной схемы."""
        if self.scheme is CollectScheme.FULL_HISTORY:
            return self.units_full_history
        return self.units_two_points

    @property
    def units_cheapest(self) -> int:
        """Цена дешёвой схемы — она же цена при `AHREFS_COLLECT_SCHEME=auto`."""
        return min(self.units_full_history, self.units_two_points)


def choose_scheme(
    *,
    period_start: date,
    period_end: date,
    spec: EndpointSpec,
    windows: PointWindows,
    max_history_months: int,
    mode: CollectSchemeMode,
) -> SchemeChoice:
    """Как собирать один проект. Решение возвращается с обеими ценами и причиной.

    Правила, в порядке применения:

    1. `mode="history"` — схема выключена флагом. Цена точек всё равно
       считается: отчёт показывает, сколько прогон стоил бы при `auto` (Z6 в
       `docs/FINDINGS.md` — почему флаг вообще существует);
    2. история не дороже точек — история целиком: при равной цене она даёт ещё
       и график, а проект, собранный точками, придётся докупать в Ф4;
    3. иначе — две точки.

    **Перекрытия окон отдельным правилом нет, и это доказано, а не забыто.**
    Окна перекрываются, когда строк в периоде меньше `2 × purchased`, то есть
    не больше `2p−1`. Тогда история стоит не больше `(2p−1) × цена_строки`, а
    точки — ровно `2p × цена_строки` (минимум за запрос только увеличивает
    цену точек). Разница в цену одной строки в пользу истории, значит правило
    цены **само** выбирает историю всюду, где окна перекрылись бы. Отдельная
    ветка была бы недостижимой, а недостижимая ветка расходится с реальностью
    молча. Факт перекрытия остаётся в объяснении: оператору он полезен, потому
    что показывает, почему точки для такого периода бессмысленны.
    """
    floor = _shift_months(period_end, -max_history_months)
    lead_from = max(_shift_months(period_start, -windows.baseline_months), floor)
    purchased = max(windows.point_months, spec.rows_under_minimum())

    full = Window(date_from=lead_from, date_to=period_end)
    # Конец окна точки А считается от **двух** якорей: от старта работ (там его
    # ждёт `classify/points.py`) и от начала самого окна, если глубина истории
    # сдвинула его вперёд. Без второго якоря окно переворачивалось на проектах
    # длиннее доступной истории — см. `Window.__post_init__`.
    point_a = Window(
        date_from=lead_from,
        date_to=min(
            max(
                _shift_months(period_start, purchased - 1),
                _shift_months(lead_from, purchased - 1),
            ),
            period_end,
        ),
    )
    point_b = Window(
        date_from=max(_shift_months(period_end, -(purchased - 1)), floor),
        date_to=period_end,
    )

    units_full = spec.estimate_units(full.rows)
    units_points = spec.estimate_units(point_a.rows) + spec.estimate_units(point_b.rows)
    prices = f"история {units_full}, точки {units_points}"

    # Решение собирается в переменные и возвращается одним выражением: четыре
    # почти одинаковых `return` с пятью полями каждый — готовая находка гейта
    # копипаста, а расходятся такие ветки молча.
    overlap = point_a.date_to >= point_b.date_from
    if mode == "history":
        scheme = CollectScheme.FULL_HISTORY
        reason = f"схема выключена флагом AHREFS_COLLECT_SCHEME=history ({prices})"
    elif units_full <= units_points:
        scheme = CollectScheme.FULL_HISTORY
        crowded = "; окна точек при таком периоде перекрылись бы" if overlap else ""
        reason = (
            f"период {full.rows} стр. — история не дороже точек и даёт график "
            f"даром{crowded} ({prices})"
        )
    else:
        scheme = CollectScheme.TWO_POINTS
        reason = (
            f"период {full.rows} стр. — две точки по {purchased} мес. дешевле истории "
            f"на {units_full - units_points} units ({prices})"
        )

    windows_of = {
        CollectScheme.FULL_HISTORY: (full,),
        CollectScheme.TWO_POINTS: (point_a, point_b),
    }
    return SchemeChoice(
        scheme=scheme,
        windows=windows_of[scheme],
        units_full_history=units_full,
        units_two_points=units_points,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class SchemeBreakdown:
    """Смета в разрезе способа сбора — требование заказчика к экрану Ф6.

    Без разбивки смета выглядит произвольной: два похожих проекта стоят
    по-разному, и объяснения нет. Числа те же, что у планировщика, потому что
    берутся из тех же решений, а не считаются во второй раз.
    """

    projects: Mapping[CollectScheme, int]
    units: Mapping[CollectScheme, int]
    units_if_auto: int
    """Сколько стоил бы прогон, если бы схему выбирали по цене."""

    units_if_history: int
    """Сколько стоил бы прогон одной историей — число, с которым сравнивают."""

    def as_lines(self) -> list[str]:
        """Строки отчёта. Способ, цена группы и то, чего стоит альтернатива."""
        parts = [
            f"{scheme.value}: {count} проект(ов), {self.units.get(scheme, 0)} units"
            for scheme, count in self.projects.items()
            if count
        ]
        lines = [f"схема сбора — {'; '.join(parts) if parts else 'нечего собирать'}"]
        if self.units_if_auto != self.units_if_history:
            lines.append(
                f"при AHREFS_COLLECT_SCHEME=auto прогон стоил бы {self.units_if_auto} "
                f"units против {self.units_if_history} историей "
                f"(экономия {self.units_if_history - self.units_if_auto})"
            )
        return lines

    def per_100_urls(self, projects: int) -> int:
        """«Стоимость запуска на 100 URL» — метрика приёмки, названная заказчиком.

        Считается от числа проектов в прогоне, а не только для ровно ста:
        сравнивать прогоны между собой иначе нельзя, а именно за этим число и
        нужно. Ноль проектов даёт ноль, а не деление на ноль.
        """
        if projects <= 0:
            return 0
        total = sum(self.units.values())
        return round(total / projects * 100)


def breakdown(
    choices: Mapping[int, SchemeChoice],
    units_by_project: Mapping[int, int],
) -> SchemeBreakdown:
    """Свернуть решения по проектам в смету по способам.

    Считает **проекты**, а не задачи: в схеме «две точки» у проекта два запроса
    одним endpoint'ом, и «проектов 3, собрано 6» — то самое число, которое
    нельзя показать человеку (урок L13).

    Units берутся из реальных задач плана (`units_by_project`), а не из цены
    решения: между решением и задачей стоит кэш, и проект с уже купленным окном
    обязан входить в смету нулём. Считать цену второй раз по решению значило бы
    показать оператору смету, которой прогон не соответствует.
    """
    projects: dict[CollectScheme, int] = dict.fromkeys(CollectScheme, 0)
    units: dict[CollectScheme, int] = dict.fromkeys(CollectScheme, 0)
    for project_id, choice in choices.items():
        projects[choice.scheme] += 1
        units[choice.scheme] += units_by_project.get(project_id, 0)
    return SchemeBreakdown(
        projects=projects,
        units=units,
        units_if_auto=sum(choice.units_cheapest for choice in choices.values()),
        units_if_history=sum(choice.units_full_history for choice in choices.values()),
    )


def _shift_months(anchor: date, months: int) -> date:
    """Первое число месяца, сдвинутого на `months` от `anchor`.

    Живёт здесь, а не в `plan.py`, потому что вся арифметика границ периода —
    это правило предметной области («сколько истории нужно кейсу»), и второй её
    экземпляр разошёлся бы с первым при правке окон.
    """
    total = anchor.year * 12 + (anchor.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)
