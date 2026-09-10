"""Настройки классификации: где лежит сид порогов.

Сами пороги живут в БД версионированными записями (`Ruleset`) и правятся людьми —
файл нужен только для первого запуска и как справочник по структуре.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from ahrefs_cases.config._base import Settings


class ClassifySettings(Settings):
    """Сид порогов и окна расчёта точек А/Б по умолчанию."""

    thresholds_seed_path: Path = Field(
        Path("./config/thresholds.default.yml"), validation_alias="THRESHOLDS_SEED_PATH"
    )
    """По умолчанию — нейтральные умолчания из репозитория, НЕ пороги заказчика.

    Пороги Приложения А лежат в `config/thresholds.example.yml`, который по
    варианту D в git не уезжает: это данные клиента. Указать их — задача
    развёртывания (`THRESHOLDS_SEED_PATH`), а не значение по умолчанию.

    Найдено красным CI: golden-таблица стояла на клиентском файле и падала
    там, где его нет по построению. Локально всё было зелёным."""
