"""Сценарии синтетических серий: формы, на которых проверяется классификация.

Семь форм из §1a документа реализации. Каждая описана **данными** — множителем
роста, длиной истории, дырами, хвостовым провалом. Ветвления по имени сценария
здесь нет намеренно: восьмая форма должна добавляться строкой в таблице, иначе
генератор станет местом, где формы незаметно расходятся с ожиданиями Ф3.

Важно, чего эти данные не заменяют: настоящих странностей Ahrefs. Фикстуры
рисуют формы, которые мы **задали**; живые данные покажут формы, которые
случились. Поэтому Ф7 — отдельная фаза, а не галочка (§1a).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ScenarioName(StrEnum):
    """Имена сценариев. Значение = ключ в `data/fixtures/scenarios.yml`."""

    STEADY_GROWTH = "steady_growth"
    WEAK_GROWTH = "weak_growth"
    DECLINE = "decline"
    SHORT_HISTORY = "short_history"
    DATA_HOLE = "data_hole"
    LATE_DROP = "late_drop"
    BACKLINK_SPIKE = "backlink_spike"
    EMPTY = "empty"
    """Домен без истории: молодой сайт или Ahrefs его не знает. Не форма, а её
    отсутствие — но приходит из того же места и обязана обрабатываться штатно
    (пример B11), иначе один такой домен уронит прогон на сотню."""


@dataclass(frozen=True, slots=True)
class ScenarioShape:
    """Форма серии в множителях к начальному уровню.

    `traffic_growth` — во сколько раз трафик меняется к концу истории;
    `holes` — индексы месяцев, которых в серии **не будет** (не нули);
    `tail_factor` — множитель к последним `tail_months` точкам.
    """

    traffic_growth: float
    months: int = 18
    refdomains_growth: float = 1.2
    holes: tuple[int, ...] = field(default_factory=tuple)
    tail_factor: float = 1.0
    tail_months: int = 0
    spike_month: int | None = None
    """Месяц скачка ссылочного: `refdomains` прыгает втрое и остаётся."""


SHAPES: dict[ScenarioName, ScenarioShape] = {
    ScenarioName.STEADY_GROWTH: ScenarioShape(traffic_growth=2.6, refdomains_growth=1.9),
    ScenarioName.WEAK_GROWTH: ScenarioShape(traffic_growth=1.12, refdomains_growth=1.1),
    ScenarioName.DECLINE: ScenarioShape(traffic_growth=0.68, refdomains_growth=0.95),
    ScenarioName.SHORT_HISTORY: ScenarioShape(traffic_growth=1.8, months=4),
    ScenarioName.DATA_HOLE: ScenarioShape(traffic_growth=2.1, holes=(5, 6, 7)),
    ScenarioName.LATE_DROP: ScenarioShape(
        traffic_growth=2.2, tail_factor=0.35, tail_months=2, refdomains_growth=1.6
    ),
    ScenarioName.BACKLINK_SPIKE: ScenarioShape(
        traffic_growth=1.45, refdomains_growth=3.4, spike_month=8
    ),
    ScenarioName.EMPTY: ScenarioShape(traffic_growth=1.0, months=0),
}
"""Числа подобраны против порогов Приложения А, но пороги Ф3 будут писаться
против **этих форм**, а не наоборот: подгонять сценарии под пороги значит
получить классификатор, который проходит собственные данные и ошибается на
чужих."""

DEFAULT_SCENARIO = ScenarioName.STEADY_GROWTH
