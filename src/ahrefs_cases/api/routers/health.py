"""Health: три состояния, различимые снаружи."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ahrefs_cases import config
from ahrefs_cases.storage import get_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

_PROBE_TIMEOUT_SEC = 3.0


async def _migration_revision() -> str | None:
    """Текущая ревизия схемы или None, если база недоступна.

    Своё короткое соединение, а не сессия из зависимости: зависимость падает
    ДО тела обработчика (и на выходе из него), и тогда health отвечает 500 —
    то есть именно тогда, когда должен сказать «база недоступна», он говорит
    «я сломан». Поймано примером A3 при первом прогоне.
    """
    engine = get_engine()
    try:
        async with asyncio.timeout(_PROBE_TIMEOUT_SEC), engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            return str(result.scalar_one())
    except Exception as exc:
        # Тип исключения намеренно широкий: до базы можно не дойти и OSError'ом
        # (порт закрыт), и TimeoutError, и SQLAlchemyError. Молчания при этом нет —
        # причина уходит в лог и в тело ответа.
        logger.warning("health: база недоступна (%s): %s", type(exc).__name__, exc)
        return None


@router.get("/api/health")
async def health(response: Response) -> dict[str, Any]:
    """`200` с версией миграции; `503` с причиной, если база недоступна."""
    revision = await _migration_revision()
    if revision is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unavailable",
            "reason": "database unreachable",
            "provider": config.ahrefs.provider,
        }
    return {
        "status": "ok",
        "migration": revision,
        "provider": config.ahrefs.provider,
    }
