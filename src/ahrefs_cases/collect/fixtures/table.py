"""Таблица «домен → сценарий»: какие данные увидит прогон по каждому домену.

Назначение явное, а не по хэшу домена. Хэш дал бы ту же воспроизводимость и
меньше файлов, но тест Ф3 «почему у d47 группа medium» пришлось бы читать через
вычисление хэша, а не глазами. Список правится руками — значит он должен
читаться руками.

Домена нет в таблице — берётся `default`. Это не молчаливое умолчание: прогон
на списке заказчика (реальные домены, которых в таблице нет) должен что-то
показать в fixture-режиме, иначе демонстрировать сервис до Ф7 нечем.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ahrefs_cases import config
from ahrefs_cases.collect.fixtures.scenarios import DEFAULT_SCENARIO, ScenarioName

_TABLE_FILE = "scenarios.yml"


class ScenarioTableError(ValueError):
    """Таблица есть, но её нельзя применить: неизвестный сценарий, битый YAML.

    Отдельный тип, потому что молчаливый откат к `default` здесь опасен: прогон
    прошёл бы «успешно», нарисовав всем доменам одну и ту же форму, и Ф3
    показала бы стопроцентное согласие с порогами.
    """


@dataclass(frozen=True, slots=True)
class ScenarioTable:
    """Назначения сценариев и зерно генератора."""

    assignments: dict[str, ScenarioName]
    default: ScenarioName = DEFAULT_SCENARIO
    seed: int = 42

    def scenario_for(self, domain: str) -> ScenarioName:
        return self.assignments.get(domain.lower(), self.default)


def load_table(path: Path | None = None) -> ScenarioTable:
    """Прочитать таблицу. Нет файла — пустая таблица с дефолтом, а не отказ."""
    source = path or Path(config.ahrefs.fixtures_dir) / _TABLE_FILE
    if not source.exists():
        return ScenarioTable(assignments={}, seed=config.ahrefs.fixture_seed)

    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    return ScenarioTable(
        assignments=_parse_assignments(raw.get("domains") or {}, source),
        default=_parse_scenario(raw.get("default"), source) or DEFAULT_SCENARIO,
        seed=int(raw.get("seed", config.ahrefs.fixture_seed)),
    )


def _parse_assignments(raw: object, source: Path) -> dict[str, ScenarioName]:
    if not isinstance(raw, dict):
        raise ScenarioTableError(f"{source}: раздел `domains` должен быть словарём")
    assignments: dict[str, ScenarioName] = {}
    for domain, value in raw.items():
        scenario = _parse_scenario(value, source)
        if scenario is None:
            raise ScenarioTableError(f"{source}: у домена {domain} пустой сценарий")
        assignments[str(domain).lower()] = scenario
    return assignments


def _parse_scenario(value: object, source: Path) -> ScenarioName | None:
    if value is None:
        return None
    try:
        return ScenarioName(str(value))
    except ValueError as exc:
        known = ", ".join(sorted(name.value for name in ScenarioName))
        raise ScenarioTableError(
            f"{source}: неизвестный сценарий {value!r}. Известные: {known}"
        ) from exc
