"""Алерты в Telegram: бот и чат, куда пишет реапер об упавших прогонах.

Ту же пару читают скрипты хоста (`scripts/notify.sh`): бэкап и сторож здоровья
живут вне контейнеров и о своих бедах пишут в тот же чат.

Не задано ничего — канал выключен, и это законно: дев-стенд, CI. Задана одна
переменная из двух — канал тоже выключен, но реапер говорит об этом на старте
ошибкой в журнале, а не роняет сервис: опечатка в необязательном канале не
стоит остановленного API.
"""

from __future__ import annotations

from pydantic import Field, SecretStr

from ahrefs_cases.config._base import Settings


class AlertSettings(Settings):
    telegram_bot_token: SecretStr = Field(SecretStr(""), validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field("", validation_alias="TELEGRAM_CHAT_ID")
    # Меняют только тесты: вместо Telegram — свой сервер.
    telegram_api_url: str = Field("https://api.telegram.org", validation_alias="TELEGRAM_API_URL")

    @property
    def enabled(self) -> bool:
        return bool(self.telegram_bot_token.get_secret_value() and self.telegram_chat_id)

    @property
    def missing_half(self) -> str:
        """Имя недостающей переменной, если пара задана наполовину; иначе пусто."""
        token = bool(self.telegram_bot_token.get_secret_value())
        if token == bool(self.telegram_chat_id):
            return ""
        return "TELEGRAM_CHAT_ID" if token else "TELEGRAM_BOT_TOKEN"
