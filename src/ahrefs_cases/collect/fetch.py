"""Исход одной задачи: запрос, разбор ошибок, короткая история.

Отдельно от прогона, потому что это другой масштаб: прогон отвечает за сотню
доменов, чекпойнты и журнал, а здесь — что случилось с одним запросом и как это
назвать. Раннер второй раз упёрся в лимит длины файла, и оба раза лимит
показывал настоящую границу, а не мешал.

Правило тут одно и оно дорогое: **исключение по одной задаче — это исход
задачи, а не конец прогона**. Ошибка одного домена не имеет права уронить сбор
по остальным девяноста девяти, но и молчать о ней нельзя — причина уезжает в
`RunItem` и видна в отчёте.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ahrefs_cases.collect.ahrefs_transport import AhrefsHTTPError, AhrefsUnavailableError
from ahrefs_cases.collect.plan import CollectTask
from ahrefs_cases.collect.provider import AhrefsProvider, HistoryResult
from ahrefs_cases.storage._enums import RunItemOutcome

logger = logging.getLogger(__name__)

SHORT_HISTORY_POINTS = 6
"""Ниже этого числа месяцев история считается короткой и помечается в `RunItem`.

Пометка, а не пропуск: годится ли такая история для кейса, решает классификация
(Ф3) по порогам Приложения А — у сбора нет ни порогов, ни права их применять.
Сбор обязан только не молчать об этом.
"""


@dataclass(slots=True)
class TaskOutcome:
    """Что вышло по одной задаче. Складывается в журнал одним местом ниже."""

    task: CollectTask
    outcome: RunItemOutcome
    reason: str = ""
    result: HistoryResult | None = None


async def fetch_one(provider: AhrefsProvider, task: CollectTask) -> TaskOutcome:
    """Один запрос. Исключение здесь — исход задачи, а не конец прогона."""
    try:
        result = await provider.fetch_history(task.spec, task.request)
    except (AhrefsUnavailableError, AhrefsHTTPError) as exc:
        logger.warning(
            "collect_task_failed",
            extra={"domain": task.domain, "endpoint": task.spec.name, "reason": str(exc)},
        )
        return TaskOutcome(task=task, outcome=RunItemOutcome.FAILED, reason=str(exc))
    except Exception as exc:
        # Неизвестная ошибка (разбор ответа, кодировка, чужая библиотека) не
        # имеет права уронить прогон на сотню доменов. Логируется целиком со
        # стеком: свернуть незнакомое в строку — значит потерять единственный
        # шанс понять, что это было. `BaseException` сюда не попадает, поэтому
        # отмена прогона остаётся отменой, а не «падением по своей вине».
        logger.exception(
            "collect_task_crashed",
            extra={"domain": task.domain, "endpoint": task.spec.name},
        )
        return TaskOutcome(
            task=task,
            outcome=RunItemOutcome.FAILED,
            reason=f"неожиданная ошибка {type(exc).__name__}: {exc}",
        )

    if result.is_empty:
        return TaskOutcome(
            task=task,
            outcome=RunItemOutcome.SKIPPED_NO_DATA,
            reason="Ahrefs не отдал историю по домену",
            result=result,
        )

    months = len(result.points)
    reason = f"short_history: {months} мес." if months < SHORT_HISTORY_POINTS else ""
    return TaskOutcome(task=task, outcome=RunItemOutcome.OK, reason=reason, result=result)
