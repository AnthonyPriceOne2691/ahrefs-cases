"""Хранилище: модели, перечисления домена, сессии.

Ф1 — модели и миграции. Репозитории приходят вместе с логикой, которая их
использует: слой доступа без потребителя проектируется наугад.
"""

from __future__ import annotations

from ahrefs_cases.storage import models
from ahrefs_cases.storage._enums import (
    ArtifactFormat,
    CaseStatus,
    Group,
    LedgerKind,
    Metric,
    MetricSource,
    ProjectStatus,
    RunItemOutcome,
    RunStatus,
    TargetMode,
    UserGroup,
)
from ahrefs_cases.storage.session import dispose_engine, get_engine, get_sessionmaker, session_scope

__all__ = [
    "ArtifactFormat",
    "CaseStatus",
    "Group",
    "LedgerKind",
    "Metric",
    "MetricSource",
    "ProjectStatus",
    "RunItemOutcome",
    "RunStatus",
    "TargetMode",
    "UserGroup",
    "dispose_engine",
    "get_engine",
    "get_sessionmaker",
    "models",
    "session_scope",
]
