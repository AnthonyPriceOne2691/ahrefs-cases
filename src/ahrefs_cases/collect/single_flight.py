"""Single-flight: два прогона по одному домену делают один запрос.

Один домен закажут разные отделы — это прямое требование §5 документа
реализации («дедупликация между прогонами»). Пока прогоны идут в одном
процессе, дедупликация сводится к простому правилу: если запрос с такими же
параметрами уже в полёте, второй ждёт его результат вместо своего.

Сделано обёрткой над провайдером, а не правкой исполнителя: исполнитель ничего
не знает о дедупликации, а обёртка проверяется отдельно от прогона. Ключ —
полный набор параметров запроса: два прогона с **разными** `date_from` просят
разные данные, и склеивать их нельзя.

Граница честная: блокировка внутрипроцессная. Два воркера в Ф5 потребуют
общего замка (Redis SETNX) — до тех пор второй процесс просто не запускается,
и это записано в спеке, а не подразумевается.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.provider import AhrefsProvider, HistoryRequest, HistoryResult
from ahrefs_cases.storage._enums import MetricSource

logger = logging.getLogger(__name__)

_Key = tuple[str, str, str, str, str, str]


@dataclass(eq=False)
class SingleFlightProvider:
    """Провайдер, склеивающий одинаковые запросы, идущие одновременно."""

    inner: AhrefsProvider

    def __post_init__(self) -> None:
        self._inflight: dict[_Key, asyncio.Task[HistoryResult]] = {}

    @property
    def source(self) -> MetricSource:
        return self.inner.source

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        """Один запрос на ключ, сколько бы ни было желающих.

        Ожидающий получает **тот же** объект результата. Это безопасно, потому
        что `HistoryResult` неизменяем: иначе один прогон правил бы данные
        другого, и найти такое было бы почти невозможно.
        """
        key = _key(spec, request)
        task = self._inflight.get(key)
        if task is not None:
            logger.info(
                "collect_single_flight_join",
                extra={"domain": request.target, "endpoint": spec.name},
            )
            return await asyncio.shield(task)

        task = asyncio.create_task(self.inner.fetch_history(spec, request))
        self._inflight[key] = task
        try:
            return await task
        finally:
            # Снимаем ключ в `finally`, а не после успеха: упавший запрос не
            # должен навсегда заблокировать домен — иначе одна ошибка сделала
            # бы его неопрашиваемым до перезапуска процесса.
            self._inflight.pop(key, None)


def _key(spec: EndpointSpec, request: HistoryRequest) -> _Key:
    """Ключ склейки — полный набор параметров запроса.

    `date_from` входит в ключ обязательно: два прогона по одному домену могут
    просить разные окна (один инкрементально, другой с `--refresh`), и выдать
    второму чужой ответ значило бы молча отдать не те данные.
    """
    return (
        spec.name,
        request.target,
        request.mode.value,
        request.country,
        request.date_from.isoformat(),
        request.date_to.isoformat() if request.date_to else "",
    )
