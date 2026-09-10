"""Настройки доступа к Ahrefs: провайдер, ключ, таймауты, экономия units.

Провайдер по умолчанию `fixture` — разработка идёт без ключа, без сети и без
расхода квоты заказчика. Переключение в `live` — решение человека (см.
`delivery/CONSTITUTION.md`, agent-permissions).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from ahrefs_cases.config._base import Settings

Provider = Literal["fixture", "live"]
HistoryGrouping = Literal["daily", "weekly", "monthly"]


class AhrefsSettings(Settings):
    """Конфиг слоя `collect`. Дефолты подобраны так, чтобы без .env работал fixture."""

    provider: Provider = Field("fixture", validation_alias="AHREFS_PROVIDER")
    api_key: str = Field("", validation_alias="AHREFS_API_KEY")
    base_url: str = Field("https://api.ahrefs.com", validation_alias="AHREFS_BASE_URL")
    timeout_sec: float = Field(60.0, gt=0, validation_alias="AHREFS_TIMEOUT_SEC")
    retry_count: int = Field(3, ge=1, le=10, validation_alias="AHREFS_RETRY_COUNT")
    retry_backoff_sec: tuple[float, ...] = Field(
        (1.0, 5.0, 30.0), validation_alias="AHREFS_RETRY_BACKOFF_SEC"
    )

    # --- fixture-режим (docs/IMPLEMENTATION_V3.md §1a) ---
    fixtures_dir: str = Field("data/fixtures", validation_alias="AHREFS_FIXTURES_DIR")
    """Где лежит таблица сценариев. Путь в конфиге, а не вычисление от `__file__`:
    иначе он ломается при установке пакета и при запуске из другого каталога."""

    fixture_seed: int = Field(42, validation_alias="AHREFS_FIXTURE_SEED")
    """Зерно генератора. Поле конфига, потому что менять его придётся осознанно:
    смена seed переписывает все синтетические серии, а на них стоят golden-тесты Ф3."""

    # --- экономия units (docs/UNITS_ECONOMY.md) ---
    units_min_left: int = Field(5000, ge=0, validation_alias="AHREFS_UNITS_MIN_LEFT")
    history_grouping: HistoryGrouping = Field("monthly", validation_alias="AHREFS_HISTORY_GROUPING")
    max_history_months: int = Field(24, ge=1, le=60, validation_alias="AHREFS_MAX_HISTORY_MONTHS")
    collect_dr_history: bool = Field(False, validation_alias="AHREFS_COLLECT_DR_HISTORY")
    stage2_only_for_cases: bool = Field(True, validation_alias="AHREFS_STAGE2_ONLY_FOR_CASES")
    max_parallel: int = Field(3, ge=1, le=10, validation_alias="COLLECT_MAX_PARALLEL")

    @field_validator("retry_backoff_sec", mode="before")
    @classmethod
    def _parse_backoff(cls, value: object) -> object:
        """`1,5,30` из .env → кортеж чисел.

        Разбор отдельной функцией, а не инлайном: это единственная реальная логика
        в конфиге, и на неё есть round-trip-свойство в тестах.
        """
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return tuple(float(p) for p in parts)
        return value

    @model_validator(mode="after")
    def _live_needs_key(self) -> AhrefsSettings:
        """fail-fast: `live` без ключа падает на старте, а не на первом запросе.

        Иначе ошибка всплывает в середине платного прогона, когда часть units уже
        потрачена, и выглядит как сбой Ahrefs, а не как незаполненный конфиг.
        """
        if self.provider == "live" and not self.api_key:
            raise ValueError(
                "AHREFS_PROVIDER=live требует непустой AHREFS_API_KEY. "
                "Для разработки оставьте AHREFS_PROVIDER=fixture."
            )
        return self
