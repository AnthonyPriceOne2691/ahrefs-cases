"""HTTP-транспорт Ahrefs: запрос, ретраи, разбор заголовков стоимости.

Отделён от провайдера намеренно. Провайдер знает про endpoint'ы и метрики,
транспорт — про сеть: таймаут, повторы, коды ответа, `x-api-units-cost-*`.
Слепи их — и разбор ответа стало бы невозможно проверить без сети.

Повторяем только то, что осмысленно повторять: таймаут, обрыв соединения, 429 и
5xx. На 400 и 401 повтор бессмысленен и вреден — три попытки с неверным ключом
это три записи в журнале Ahrefs и ноль пользы.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from ahrefs_cases import config

logger = logging.getLogger(__name__)

_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_UNITS_ACTUAL_HEADER = "x-api-units-cost-total-actual"
_UNITS_TOTAL_HEADER = "x-api-units-cost-total"


class AhrefsHTTPError(RuntimeError):
    """Ответ Ahrefs, который не лечится повтором (ключ, параметры, права)."""


class AhrefsUnavailableError(RuntimeError):
    """Ahrefs недоступен после всех попыток. Прогон помечает проект `failed`,
    но не останавливается: остальные домены собрать всё ещё можно."""


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Тело ответа и то, во что он обошёлся.

    `units_actual` берётся из заголовка и является фактом. `units_estimated` —
    то, что Ahrefs оценил до выполнения; расхождение между ними и есть материал
    Ф7, поэтому оба поля хранятся, а не одно.
    """

    payload: dict[str, Any]
    units_actual: int
    units_estimated: int
    headers: Mapping[str, str] = field(default_factory=dict)
    """Заголовки ответа целиком.

    Нужны разведке Ф7: пока модель стоимости — гипотеза, важно видеть все
    `x-api-*`, а не только те два, что мы решили читать. Секретов в них нет.
    """


class AhrefsTransport:
    """Тонкий клиент: один метод, никакого знания о метриках."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._owns_client = client is None

    async def get(self, path: str, params: dict[str, str]) -> TransportResponse:
        """GET с повторами. Возвращает тело и стоимость, поднимает — только явное."""
        client = self._client or self._build_client()
        try:
            return await self._get_with_retries(client, path, params)
        finally:
            if self._owns_client:
                await client.aclose()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=config.ahrefs.base_url,
            timeout=config.ahrefs.timeout_sec,
            headers={"Authorization": f"Bearer {config.ahrefs.api_key}"},
        )

    async def _get_with_retries(
        self, client: httpx.AsyncClient, path: str, params: dict[str, str]
    ) -> TransportResponse:
        backoff = config.ahrefs.retry_backoff_sec
        attempts = config.ahrefs.retry_count
        last_reason = ""
        for attempt in range(attempts):
            try:
                response = await client.get(path, params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_reason = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "ahrefs_request_failed",
                    extra={"path": path, "attempt": attempt + 1, "reason": last_reason},
                )
            else:
                if response.status_code not in _RETRY_STATUSES:
                    return self._to_result(response, path)
                last_reason = f"HTTP {response.status_code}"
                logger.warning(
                    "ahrefs_request_retryable",
                    extra={"path": path, "attempt": attempt + 1, "status": response.status_code},
                )

            if attempt + 1 < attempts:
                await asyncio.sleep(backoff[min(attempt, len(backoff) - 1)])

        raise AhrefsUnavailableError(
            f"Ahrefs не ответил за {attempts} попыт(ок) на {path}: {last_reason}"
        )

    def _to_result(self, response: httpx.Response, path: str) -> TransportResponse:
        if response.status_code >= httpx.codes.BAD_REQUEST:
            raise AhrefsHTTPError(
                f"Ahrefs ответил {response.status_code} на {path}: {response.text[:200]}"
            )
        payload: dict[str, Any] = response.json()
        estimated = _header_int(response, _UNITS_TOTAL_HEADER)
        actual = _header_int(response, _UNITS_ACTUAL_HEADER)
        return TransportResponse(
            payload=payload,
            # Замерено: `-total-actual` приходит нулём при ненулевом `-total`
            # (три запроса подряд, `x-api-cache: miss`). Записать ноль в журнал
            # значило бы отчитаться о бесплатном прогоне: расход есть, просто
            # Ahrefs сообщает его другим заголовком. Берём `-total`, пока Ф7 не
            # покажет, когда `-total-actual` осмыслен.
            units_actual=actual or estimated,
            units_estimated=estimated,
            headers=dict(response.headers),
        )


def _header_int(response: httpx.Response, name: str) -> int:
    """Заголовок стоимости → число. Нет заголовка — ноль, но с записью в лог.

    Ноль честнее выдуманной оценки: журнал units обязан отличать «стоило ноль»
    от «мы не узнали цену», а для второго есть лог и расхождение с оценкой.
    """
    raw = response.headers.get(name)
    if raw is None:
        logger.warning("ahrefs_units_header_missing", extra={"header": name})
        return 0
    try:
        return int(raw)
    except ValueError:
        logger.warning("ahrefs_units_header_broken", extra={"header": name, "value": raw})
        return 0
