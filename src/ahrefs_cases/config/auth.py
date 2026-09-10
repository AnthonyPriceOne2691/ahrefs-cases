"""Настройки аутентификации: JWT и время жизни токена."""

from __future__ import annotations

from pydantic import Field

from ahrefs_cases.config._base import Settings


class AuthSettings(Settings):
    """JWT. Пустой секрет допустим только в fixture-разработке; проверка — на старте API."""

    jwt_secret: str = Field("", validation_alias="JWT_SECRET")
    jwt_ttl_hours: int = Field(12, ge=1, le=168, validation_alias="JWT_TTL_HOURS")
    jwt_algorithm: str = Field("HS256", validation_alias="JWT_ALGORITHM")
