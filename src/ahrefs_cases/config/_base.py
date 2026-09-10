"""Общая база настроек: чтение .env один раз и запрет читать окружение мимо этого пакета.

Правило проекта: `os.getenv` / `os.environ` вне `config/` запрещены. Причина не
стилистическая — опечатка в имени переменной вне типизированного конфига ловится
только в рантайме, и обычно на проде.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = ".env"


class Settings(BaseSettings):
    """База для доменных настроек: .env, регистр не важен, лишние ключи игнорируем.

    `extra="ignore"` осознанно: в одном .env живут переменные всех доменов, и
    каждый класс читает только свои.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )
    """`populate_by_name` обязателен, и это не удобство.

    У полей стоит `validation_alias` (имя переменной окружения), и без этого
    флага конструктор принимает ТОЛЬКО алиас: `AhrefsSettings(provider="live")`
    молча игнорировался бы вместе с `extra="ignore"`, отдавая дефолт. То есть
    проверка «live без ключа падает» была бы зелёной, ничего не проверив, —
    поймано тестом A5 при первом же прогоне.
    """
