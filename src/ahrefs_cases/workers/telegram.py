"""Сообщение в Telegram — канал алертов сервиса (`config.alerts`).

Токен бота — часть адреса запроса (`/bot<токен>/sendMessage`), а текст
исключений httpx содержит адрес. Поэтому в журнал идут только тип ошибки и код
ответа: сообщение исключения унесло бы токен в логи. Тот же канал со стороны
хоста — `scripts/notify.sh`.
"""

from __future__ import annotations

import logging

import httpx

from ahrefs_cases import config

logger = logging.getLogger(__name__)

_TIMEOUT_SEC = 20.0
_TEXT_LIMIT = 4000
"""Потолок Telegram — 4096 символов: длинную причину режем, а не теряем сообщение."""


async def send(text: str, *, transport: httpx.AsyncBaseTransport | None = None) -> bool:
    """Отправить в чат алертов. True — Telegram принял; иначе False и строка в журнале.

    Канал не настроен — False без строки: это состояние, о нём реапер говорит
    один раз на старте, а не на каждом упавшем прогоне.
    """
    settings = config.alerts
    if not settings.enabled:
        return False
    token = settings.telegram_bot_token.get_secret_value()
    url = f"{settings.telegram_api_url.rstrip('/')}/bot{token}/sendMessage"
    payload = {"chat_id": settings.telegram_chat_id, "text": text[:_TEXT_LIMIT]}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC, transport=transport) as client:
            response = await client.post(url, data=payload)
    except httpx.HTTPError as exc:
        logger.warning("telegram_unreachable", extra={"error": type(exc).__name__})
        return False
    if response.status_code != httpx.codes.OK:
        logger.warning("telegram_refused", extra={"status": response.status_code})
        return False
    return True
