"""Настройки хранилища и очереди."""

from __future__ import annotations

from pydantic import Field

from ahrefs_cases.config._base import Settings

_DEV_DSN = "postgresql+asyncpg://cases:cases@localhost:5432/cases"


class StorageSettings(Settings):
    """Postgres и Redis. Дефолты — дев-окружение из docker-compose.dev.yml."""

    database_url: str = Field(_DEV_DSN, validation_alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")
    queue_name: str = Field("cases", validation_alias="QUEUE_NAME")
    worker_concurrency: int = Field(1, ge=1, le=2, validation_alias="WORKER_CONCURRENCY")
    """Прогонов одновременно. Верхняя граница 2 — не осторожность, а арифметика:
    параллельные прогоны делят одну квоту Ahrefs и ломают смету (см.
    docs/IMPLEMENTATION_V3.md §3)."""

    echo_sql: bool = Field(False, validation_alias="DB_ECHO_SQL")
