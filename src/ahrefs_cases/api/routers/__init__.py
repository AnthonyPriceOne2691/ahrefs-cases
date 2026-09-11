"""Роутеры по `docs/IMPLEMENTATION_V3.md` §9.

Ф1 — health, Ф5 — вход и чтение. Остальные приходят вместе с логикой, которую
они открывают: роутер без реализации это ложное обещание в схеме OpenAPI.
"""

from __future__ import annotations

from ahrefs_cases.api.routers.auth import router as auth_router
from ahrefs_cases.api.routers.cases import router as cases_router
from ahrefs_cases.api.routers.health import router as health_router
from ahrefs_cases.api.routers.projects import router as projects_router
from ahrefs_cases.api.routers.runs import router as runs_router
from ahrefs_cases.api.routers.usage import router as usage_router

__all__ = [
    "auth_router",
    "cases_router",
    "health_router",
    "projects_router",
    "runs_router",
    "usage_router",
]
