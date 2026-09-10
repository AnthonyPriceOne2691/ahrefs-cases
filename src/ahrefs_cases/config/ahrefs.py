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
    current_month_ttl_hours: int = Field(
        24, ge=0, le=720, validation_alias="AHREFS_CURRENT_MONTH_TTL_HOURS"
    )
    """Как долго текущий (незакрытый) месяц считается свежим.

    Закрытый месяц не меняется никогда, и TTL по времени для него бессмыслен.
    Текущий — меняется, но не ежеминутно: без TTL два прогона в один день
    платили бы за него дважды, а шесть сотрудников из четырёх отделов запускают
    прогоны в один день регулярно."""

    stage2_min_growth: float = Field(
        1.1, ge=1.0, le=10.0, validation_alias="AHREFS_STAGE2_MIN_GROWTH"
    )
    """Порог предварительного отбора кандидатов шага 2 (во сколько раз вырос
    трафик). Это НЕ классификация: группу с объяснением даёт Ф3 по порогам
    Приложения А и переопределяет отбор. Здесь только «стоит ли платить за
    дорогие метрики»."""

    history_lead_months: int = Field(3, ge=0, le=12, validation_alias="AHREFS_HISTORY_LEAD_MONTHS")
    """Сколько месяцев истории брать ДО старта работ. Нужны точке А (среднее по
    окну вокруг границы периода) и baseline'у Ф3. По нашей модели стоимости цена
    запроса не зависит от числа строк, поэтому запас почти бесплатен — но если
    Ф7 покажет построчный биллинг, уменьшать надо будет здесь, а не в коде."""
    collect_dr_history: bool = Field(False, validation_alias="AHREFS_COLLECT_DR_HISTORY")
    stage2_only_for_cases: bool = Field(True, validation_alias="AHREFS_STAGE2_ONLY_FOR_CASES")
    max_parallel: int = Field(3, ge=1, le=10, validation_alias="COLLECT_MAX_PARALLEL")

    # --- устойчивость прогона (docs/IMPLEMENTATION_V3.md §5, «Надёжность») ---
    breaker_max_failures: int = Field(
        5, ge=1, le=100, validation_alias="COLLECT_BREAKER_MAX_FAILURES"
    )
    """Сколько неудач подряд означают «Ahrefs лёг» и пора останавливать прогон.

    Подряд, а не всего: одиночные ошибки на отдельных доменах — норма (домен без
    данных, странный ответ), а серия означает, что остальные 90 запросов уйдут
    в те же таймауты и купят те же ошибки."""

    checkpoint_every: int = Field(10, ge=1, le=1000, validation_alias="COLLECT_CHECKPOINT_EVERY")
    """Через сколько задач фиксировать собранное. Прогон, убитый между
    чекпойнтами, теряет не больше этого числа доменов — за них уже заплачено."""

    run_queued_stale_sec: int = Field(7200, ge=60, validation_alias="COLLECT_RUN_QUEUED_STALE_SEC")
    """Порог для прогонов, которые ещё не начинались.

    Мягче, чем у `running`, и это не симметрия ради симметрии: очередь законно
    держит задачу, пока идут предшественники. Мёртвой она становится, только
    если её вообще никто не подхватил."""

    empty_retry_days: int = Field(30, ge=0, le=365, validation_alias="AHREFS_EMPTY_RETRY_DAYS")
    """Как долго помнить, что у домена нет истории.

    Домен без данных не оставляет точек, поэтому обычный кэш о нём ничего не
    знает и покупает ту же пустоту каждым прогоном. Молодой сайт станет
    непустым не завтра — месяца достаточно. Дыра найдена сверкой с CRM
    агентства, где то же лечится счётчиком пустых прогонов."""

    run_stale_sec: int = Field(3600, ge=60, validation_alias="COLLECT_RUN_STALE_SEC")
    """После скольких секунд прогон в `running` считается мёртвым.

    Аналог жёсткого таймаута джобы из CRM (`run_reaper.py`): живой прогон
    физически не идёт дольше, значит признак смерти — возраст, а не отсутствие
    heartbeat'а. Поля `last_heartbeat` и миграции для этого не нужно."""

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
