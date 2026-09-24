"""Перечисления домена. Один источник: и модели, и API, и фронт читают отсюда."""

from __future__ import annotations

from enum import StrEnum


class UserGroup(StrEnum):
    """Три группы доступа. Различие сейчас одно — правка порогов.

    Группы фиксированы три, а не две: права разойдутся дальше (пользователи,
    ключи, лимиты — работа инженера, а не руководителя), и склеивать их сейчас
    значит разделять потом вместе с переписыванием проверок.
    """

    ENGINEER = "engineer"
    ADMIN = "admin"
    USER = "user"


class TargetMode(StrEnum):
    """Как считаем домен в Ahrefs. Для проекта-раздела нужен `prefix`."""

    SUBDOMAINS = "subdomains"
    PREFIX = "prefix"
    EXACT = "exact"


class ProjectStatus(StrEnum):
    NEW = "new"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    CLASSIFIED = "classified"
    CASE_READY = "case_ready"
    FAILED = "failed"
    SKIPPED = "skipped"


class Metric(StrEnum):
    """Метрики серий. Значение = имя в API и в БД одновременно."""

    ORG_TRAFFIC = "org_traffic"
    ORG_COST = "org_cost"
    KW_TOP3 = "kw_top3"
    KW_TOP4_10 = "kw_top4_10"
    KW_TOP11_20 = "kw_top11_20"
    KW_TOP21_50 = "kw_top21_50"
    KW_TOP51_PLUS = "kw_top51_plus"
    REFDOMAINS = "refdomains"
    BACKLINKS = "backlinks"
    DR = "dr"
    PAGES = "pages"
    SEARCH_VOLUME = "search_volume"


class MetricSource(StrEnum):
    """Откуда точка. `fixture` отделён от `live` намеренно: смешивать синтетику
    с оплаченными данными в одной серии нельзя — иначе непонятно, за что платили."""

    LIVE = "live"
    FIXTURE = "fixture"
    MANUAL = "manual"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunItemOutcome(StrEnum):
    OK = "ok"
    SKIPPED_NO_DATA = "skipped_no_data"
    SKIPPED_INVALID = "skipped_invalid"
    SKIPPED_QUOTA = "skipped_quota"
    SKIPPED_ABORTED = "skipped_aborted"
    """Задача не выполнялась: прогон остановлен предохранителем после серии
    неудач. Отдельный исход, а не `failed`: по этому домену мы ничего не
    спрашивали и ничего о нём не знаем — в отличие от домена, чей запрос упал."""
    FAILED = "failed"

    # Исходы ступени кейсов (сборка PDF). Собранный кейс — `ok`: журнал считает
    # «собрано» по нему, и экран сворачивает его в число так же, как у сбора.
    CASE_NOT_ELIGIBLE = "case_not_eligible"
    """Кейс не положен по группе: «плохим» по ТЗ его не собирают."""
    CASE_INSUFFICIENT_DATA = "case_insufficient_data"
    CASE_NO_VERDICT = "case_no_verdict"
    """Вердикта действующей версии порогов нет — собирать не из чего."""
    CASE_VERDICT_MISMATCH = "case_verdict_mismatch"
    """Числа вердикта не про ряды, из которых собирают кейс (Z10)."""
    CASE_BLOCKED = "case_blocked"
    """Кейс собран, но не отдан: сработал контент-запрет."""


CASE_OUTCOMES = frozenset(
    {
        RunItemOutcome.CASE_NOT_ELIGIBLE,
        RunItemOutcome.CASE_INSUFFICIENT_DATA,
        RunItemOutcome.CASE_NO_VERDICT,
        RunItemOutcome.CASE_VERDICT_MISMATCH,
        RunItemOutcome.CASE_BLOCKED,
    }
)
"""Исходы, которые пишет только сборка кейсов. Ahrefs она не спрашивает, и её
строки — не проверки домена: память о пустом домене (`cache.empty_since`) их не
считает, иначе «данных не хватило» рвало бы цепочку «нет данных» подряд."""


class Group(StrEnum):
    """Группа проекта. `INSUFFICIENT_DATA` — отдельная, не «плохая»:
    «нет данных» и «плохой результат» это разные вещи."""

    GOOD = "good"
    MEDIUM = "medium"
    POOR = "poor"
    INSUFFICIENT_DATA = "insufficient_data"


class CaseStatus(StrEnum):
    DRAFT = "draft"
    BUILT = "built"
    PUBLISHED = "published"


class ArtifactFormat(StrEnum):
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"


class LedgerKind(StrEnum):
    """Строка расхода units. `RESERVE` — смета, списанная при постановке в
    очередь: без резерва смета защищает только первого нажавшего кнопку."""

    RESERVE = "reserve"
    SPENT = "spent"
    CACHED = "cached"
