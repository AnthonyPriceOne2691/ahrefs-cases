"""Остаток квоты Ahrefs и preflight перед прогоном. Fail-closed.

`subscription-info/limits-and-usage` стоит **0 units**, поэтому спрашивать
остаток перед каждым прогоном ничего не стоит — а не спрашивать стоит дорого:
прогон, начатый вслепую, упирается в исчерпанную квоту на середине, оставив
половину проектов собранной и половину нет.

Главное правило — **fail-closed**: не смогли узнать остаток, прогон не
стартует. «Не знаем» трактуется как «не тратим»: у ошибки в эту сторону цена —
отложенный прогон, у ошибки в другую — потраченные units заказчика и
недоделанная работа.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ahrefs_cases import config
from ahrefs_cases.collect.ahrefs_transport import (
    AhrefsHTTPError,
    AhrefsTransport,
    AhrefsUnavailableError,
)
from ahrefs_cases.collect.response_guard import AhrefsResponseError, require_int

logger = logging.getLogger(__name__)

_LIMITS_PATH = "/v3/subscription-info/limits-and-usage"
_ENVELOPE_KEY = "limits_and_usage"
_UNITS_LIMIT_KEY = "units_limit_api_key"
_UNITS_USED_KEY = "units_usage_api_key"
"""Имена и вложенность замерены живым ключом 10.09.2026.

Ответ приходит обёрткой `{limits_and_usage: {...}}`, а внутри две пары чисел:
`*_workspace` — на весь воркспейс, `*_api_key` — на наш ключ. Считаем по
ключу: воркспейс делится с другими сервисами агентства, и его остаток ничего
не говорит о том, сколько можем потратить мы."""


class QuotaVerdict(StrEnum):
    """Три исхода preflight, и они разные по причине.

    `UNKNOWN` не сливается с `NOT_ENOUGH` намеренно: «квоты мало» лечится
    ожиданием или повышением лимита, «остаток неизвестен» — починкой доступа к
    Ahrefs. Слить их значит показать оператору не ту причину.
    """

    OK = "ok"
    NOT_ENOUGH = "not_enough"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class QuotaState:
    """Что известно об остатке."""

    left: int | None
    verdict: QuotaVerdict
    reason: str = ""

    @property
    def may_start(self) -> bool:
        return self.verdict is QuotaVerdict.OK


class QuotaSource(Protocol):
    """Откуда узнаём остаток. Как и у провайдера — две реализации."""

    async def units_left(self) -> int: ...


class LiveQuota:
    """Настоящий остаток из Ahrefs. Запрос бесплатный."""

    def __init__(self, transport: AhrefsTransport | None = None) -> None:
        self._transport = transport or AhrefsTransport()

    async def units_left(self) -> int:
        response = await self._transport.get(_LIMITS_PATH, {})
        # Строго: отсутствие ключа — это «мы не знаем остаток», а не «остаток
        # ноль». Разница решающая: fail-closed превратил бы ноль в вечный
        # запрет прогонов, и выглядело бы это как исчерпанная квота клиента,
        # хотя причина — наши угаданные имена полей (Z2 в docs/FINDINGS.md).
        envelope = response.payload.get(_ENVELOPE_KEY)
        if not isinstance(envelope, dict):
            message = (
                f"subscription-info: ожидали объект по ключу {_ENVELOPE_KEY!r}, "
                f"пришли ключи: {', '.join(sorted(response.payload)) or '(пусто)'}"
            )
            raise AhrefsResponseError(message)
        limit = require_int(envelope, _UNITS_LIMIT_KEY, "subscription-info")
        used = require_int(envelope, _UNITS_USED_KEY, "subscription-info")
        return max(0, limit - used)


@dataclass(frozen=True, slots=True)
class FixtureQuota:
    """Остаток в fixture-режиме. По умолчанию — бюджет первичного прогона.

    Не «бесконечность»: смета и мягкий стоп должны срабатывать в разработке,
    иначе их первое настоящее срабатывание случится на живых деньгах в Ф7.
    """

    left: int = 10_000

    async def units_left(self) -> int:
        return self.left


async def preflight(source: QuotaSource, *, needed: int, reserved: int = 0) -> QuotaState:
    """Хватит ли квоты на прогон стоимостью `needed` при уже занятых `reserved`.

    Мягкий стоп по `AHREFS_UNITS_MIN_LEFT` — не украшение: заказчику нужен
    запас на срочный ручной запрос, и прогон не должен съедать квоту до нуля.
    """
    try:
        left = await source.units_left()
    except (AhrefsUnavailableError, AhrefsHTTPError, AhrefsResponseError) as exc:
        logger.warning("quota_unknown", extra={"reason": str(exc)})
        return QuotaState(
            left=None,
            verdict=QuotaVerdict.UNKNOWN,
            reason=(
                f"остаток квоты Ahrefs неизвестен ({exc}). Прогон не начат: "
                "«не знаем» значит «не тратим». Проверьте доступность API, ключ "
                "и — если ответ пришёл, но не той формы — имена полей в спеке."
            ),
        )

    available = left - reserved
    floor = config.ahrefs.units_min_left
    if available - needed < floor:
        return QuotaState(
            left=left,
            verdict=QuotaVerdict.NOT_ENOUGH,
            reason=(
                f"не хватает units: остаток {left}, зарезервировано {reserved}, "
                f"нужно {needed}, неснижаемый запас {floor}. "
                "Прогон не начат — поднимите лимит или дождитесь других прогонов."
            ),
        )
    return QuotaState(left=left, verdict=QuotaVerdict.OK)
