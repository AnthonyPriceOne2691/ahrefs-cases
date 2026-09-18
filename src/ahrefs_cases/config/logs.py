"""Настройки логирования: формат и уровень."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ahrefs_cases.config._base import Settings


class LogSettings(Settings):
    """Как сервис рассказывает о себе.

    `json` — прод: поля из `extra` остаются полями и ищутся по имени.
    `text` — терминал: человек читает строку, поля дописываются в хвост.
    """

    format: Literal["text", "json"] = Field("text", validation_alias="LOG_FORMAT")
    level: str = Field("INFO", validation_alias="LOG_LEVEL")
