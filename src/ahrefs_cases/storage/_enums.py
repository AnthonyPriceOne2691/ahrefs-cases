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
    FAILED = "failed"


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
