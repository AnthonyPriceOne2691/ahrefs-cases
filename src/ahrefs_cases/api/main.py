"""Точка входа FastAPI. Обвязка над ядром — ядро про неё не знает."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from ahrefs_cases import config
from ahrefs_cases.api.routers import (
    alerts_router,
    auth_router,
    cases_router,
    health_router,
    projects_router,
    rulesets_router,
    runs_router,
    usage_router,
)
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.storage import dispose_engine


def _assert_config_sane() -> None:
    """Мисконфиг падает на старте, а не в середине платного прогона.

    Проверяется то, что нельзя поймать типом: непустой секрет JWT в live-режиме.
    Ключ Ahrefs при `provider=live` уже проверен валидатором конфига.
    """
    if config.ahrefs.provider == "live" and not config.auth.jwt_secret:
        raise RuntimeError(
            "live-режим без JWT_SECRET: сервис с настоящими данными не поднимается "
            "с пустым секретом подписи токенов"
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    _assert_config_sane()
    yield
    await dispose_engine()


app = FastAPI(
    title="Ahrefs Cases",
    version="0.1.0",
    lifespan=lifespan,
)
for router in (
    health_router,
    auth_router,
    projects_router,
    cases_router,
    rulesets_router,
    runs_router,
    alerts_router,
    usage_router,
):
    app.include_router(router)


@app.exception_handler(ThresholdsError)
async def _thresholds_missing(_: Request, exc: ThresholdsError) -> JSONResponse:
    """Нет активной версии порогов — это настройка, а не поломка сервиса.

    Пятисотка сказала бы «сервис сломан» и отправила бы искать дефект; здесь
    нужен `503` с причиной: пороги засеваются и утверждаются людьми, а
    классифицировать по умолчанию мы отказываемся сознательно.
    """
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)}
    )
