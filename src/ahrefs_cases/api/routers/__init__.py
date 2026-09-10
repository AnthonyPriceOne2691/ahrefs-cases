"""Роутеры по `docs/IMPLEMENTATION_V3.md` §9.

Ф1 — health. Остальные приходят вместе с логикой, которую они открывают:
роутер без реализации это ложное обещание в схеме OpenAPI.
"""

from __future__ import annotations

from ahrefs_cases.api.routers.health import router as health_router

__all__ = ["health_router"]
