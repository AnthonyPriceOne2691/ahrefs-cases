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
CollectSchemeMode = Literal["history", "auto"]


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
    units_min_left: int = Field(1000, ge=0, validation_alias="AHREFS_UNITS_MIN_LEFT")
    """Неснижаемый остаток units: запас на срочный ручной запрос аналитика.

    Был 5000 — половина всего бюджета заказчика (10 000 на первичный прогон).
    По нашей же модели стоимости первичный прогон стоит ≈ 9650 units, поэтому
    preflight отказывал бы на первом реальном запуске: 10 000 − 9650 < 5000.
    Сервис исправно не работал бы, а причина выглядела бы как нехватка квоты
    у заказчика (Z4 в docs/FINDINGS.md).

    Тысяча — это примерно двадцать ручных запросов истории: запас есть, а
    прогон проходит. Число уточняется в Ф7, когда станет известна настоящая
    цена запроса."""
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

    history_lead_months: int = Field(0, ge=0, le=12, validation_alias="AHREFS_HISTORY_LEAD_MONTHS")
    """Сколько месяцев истории брать ДО старта работ, **сверх** запаса, который
    просят пороги (`windows.pre_start_baseline_months`).

    Было 3 безусловных, стало 0. Прежний докстринг обещал: «если Ф7 покажет
    построчный биллинг, уменьшать надо будет здесь». Ф7 показал — 33 units на
    домен при цене строки 11. Потребителя у запаса нет: точка А считается окном
    **вперёд** от `period_start` (`classify/points.py`), а расчёт baseline'а
    выключен (`pre_start_baseline_months: 0`) и появится в Ф3б. Кто запас
    просит, тот его и называет — версией порогов."""

    collect_scheme: CollectSchemeMode = Field("history", validation_alias="AHREFS_COLLECT_SCHEME")
    """Как покупать историю **шага 1**: `history` — целиком, `auto` — дешевле из
    «целиком» и «две точки».

    Область флага — только шаг 1, и это не упущение. Шаг 2 выбирает схему по
    цене всегда, потому что запрещать там нечего: флаг существует из-за Z6 —
    дыры в серии трафика, — а правило достоверности серии считает
    `max_series_gap_months` только по `org_traffic`. Флаг, который молча не
    действует на половину прогона, был бы той же ловушкой, что нереализованная
    нормализация (урок L33).

    Умолчание `history` — нынешнее поведение, и это не осторожность, а Z6 в
    `docs/FINDINGS.md`: проект, собранный точками, имеет дыру во всю середину
    периода, а правило достоверности серии (`max_series_gap_months`) считает
    такую дыру недостоверной серией. Пока классификация не различает дыру
    «не покупали» от дыры «у Ahrefs нет данных», `auto` означает дешёвый сбор
    без кейсов. Планировщик и смета при этом считаются всегда: отчёт показывает,
    сколько прогон стоил бы при `auto`."""
    collect_dr_history: bool = Field(False, validation_alias="AHREFS_COLLECT_DR_HISTORY")
    collect_pages_history: bool = Field(False, validation_alias="AHREFS_COLLECT_PAGES_HISTORY")
    collect_search_volume: bool = Field(False, validation_alias="AHREFS_COLLECT_SEARCH_VOLUME")
    """Три endpoint'а шага 2, выключенные по умолчанию, — по 50 units за домен каждый.

    Ни `pages`, ни `search_volume`, ни `dr` не участвуют в правилах
    классификации и не входят в блоки кейса по ТЗ (гео, период, задача, что
    сделали, А → Б по трафику, позициям и ссылкам). На тридцати кандидатах
    это 3000 units — треть бюджета первичного прогона за данные, которые
    никто не читает.

    Включаются осознанно, когда для них появится потребитель (Z4 в
    docs/FINDINGS.md)."""
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

    estimate_tolerance_pct: float = Field(
        20.0, ge=0, le=1000, validation_alias="AHREFS_ESTIMATE_TOLERANCE_PCT"
    )
    """На сколько процентов смета может расходиться с фактом молча.

    Модель стоимости — гипотеза до Ф7 (H1 в docs/FINDINGS.md): документация
    называет и минимум 50 units, и отдельную цену `refdomains-history` в 5, не
    объясняя, как они сочетаются. Расхождение больше этого порога означает,
    что модель неверна, — и узнать об этом надо в первом же живом прогоне, а
    не из счёта в конце месяца."""

    checkpoint_every: int = Field(10, ge=1, le=1000, validation_alias="COLLECT_CHECKPOINT_EVERY")
    """Через сколько задач фиксировать собранное. Прогон, убитый между
    чекпойнтами, теряет не больше этого числа доменов — за них уже заплачено."""

    run_queued_stale_sec: int = Field(7200, ge=60, validation_alias="COLLECT_RUN_QUEUED_STALE_SEC")
    """Порог для прогонов, которые ещё не начинались.

    Мягче, чем у `running`, и это не симметрия ради симметрии: очередь законно
    держит задачу, пока идут предшественники. Мёртвой она становится, только
    если её вообще никто не подхватил."""

    empty_confirmations: int = Field(2, ge=1, le=10, validation_alias="AHREFS_EMPTY_CONFIRMATIONS")
    """Сколько пустых ответов подряд нужно, чтобы поверить в отсутствие истории.

    Один пустой ответ означает не только «домен молодой»: так же выглядят
    опечатка в домене, неверный параметр запроса и расхождение формы ответа с
    нашей спекой. Поверить с первого раза — значит замолчать проблему на
    `empty_retry_days` дней (H5 в docs/FINDINGS.md).

    Паттерн из CRM агентства: там счётчик `consecutive_zero_runs` служит той же
    цели — отличить «данных нет» от «что-то не так с запросом»."""

    empty_retry_days: int = Field(30, ge=0, le=365, validation_alias="AHREFS_EMPTY_RETRY_DAYS")
    """Как долго помнить, что у домена нет истории.

    Домен без данных не оставляет точек, поэтому обычный кэш о нём ничего не
    знает и покупает ту же пустоту каждым прогоном. Молодой сайт станет
    непустым не завтра — месяца достаточно. Дыра найдена сверкой с CRM
    агентства, где то же лечится счётчиком пустых прогонов."""

    run_timeout_sec: int = Field(14_400, ge=60, validation_alias="COLLECT_RUN_TIMEOUT_SEC")
    """Жёсткий лимит длительности одного прогона (по умолчанию 4 часа).

    Существует ради реапера. Тот судит о смерти по возрасту прогона, и это
    работает, только если живой прогон **физически не может** идти дольше
    порога. В CRM такую гарантию давал таймаут RQ-джобы; у нас очереди нет до
    Ф5, поэтому лимит держит сам прогон.

    Расчёт худшего случая шага 1: 100 доменов ÷ 3 параллельно × (60 с таймаут ×
    3 попытки + 36 с backoff) = 120 минут. Четыре часа дают двукратный запас
    и на шаг 2 (четыре endpoint'а по кандидатам)."""

    run_stale_sec: int = Field(16_200, ge=60, validation_alias="COLLECT_RUN_STALE_SEC")
    """После скольких секунд прогон в `running` считается мёртвым.

    Обязан быть **строго больше** `run_timeout_sec` — иначе реапер добивает
    работающий прогон: помечает его `failed`, освобождает резерв units, а
    прогон продолжает писать в базу, не зная об этом. Инвариант проверяется
    ниже и падает на старте, потому что подобрать несогласованные числа
    молча — ровно то, как дефект и появился (Z1 в docs/FINDINGS.md)."""

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
    def _reaper_must_outlive_the_run(self) -> AhrefsSettings:
        """Порог реапера строго больше лимита прогона — иначе отказ на старте.

        Не предупреждение и не «по умолчанию нормально»: при нарушении сервис
        убивает собственные платные прогоны на середине, и заметить это можно
        только по недобранным данным.
        """
        if self.run_stale_sec <= self.run_timeout_sec:
            message = (
                f"COLLECT_RUN_STALE_SEC={self.run_stale_sec} должен быть строго больше "
                f"COLLECT_RUN_TIMEOUT_SEC={self.run_timeout_sec}: иначе реапер пометит "
                "работающий прогон мёртвым, освободит его резерв units, а прогон "
                "продолжит писать в базу. Оставьте запас хотя бы в несколько минут."
            )
            raise ValueError(message)
        return self

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
