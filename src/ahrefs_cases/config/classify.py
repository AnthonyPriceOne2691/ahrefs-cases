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
        Path("./config/thresholds.example.yml"), validation_alias="THRESHOLDS_SEED_PATH"
    )
