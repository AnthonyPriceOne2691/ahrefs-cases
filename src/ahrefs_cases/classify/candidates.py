"""Кому покупать дорогие метрики шага 2.

Решение принимает **классификация**, а не отдельный префильтр, и это правка
14.09.2026 по итогам калибровочного прогона. До неё отбор жил в
`collect/funnel.py` и считал рост крайними точками ряда (`последняя / первая`),
тогда как вердикт считает средними по окнам версии порогов. На монотонной серии
это одно и то же, на сезонной — разные числа:

```
wineverygame.com   воронка 0.93×   классификация 1.86×
wickes.co.uk       воронка 1.03×   классификация 1.48×   (порог воронки 1.10×)
```

Оба проекта остались без подтверждающих метрик, а `good` требует хотя бы одной —
значит потолком стал `medium`, и не по результату проекта, а по решению
дешёвого префильтра. В объяснении вердикта это выглядело как несработавшая
метрика: «подтверждающая — факт —».

Правило теперь одно: **кандидат — тот, кого действующие пороги уже не считают
«плохим» по тому, что куплено на шаге 1.** Дешевле не стало и дороже тоже: тот
же один проход по сериям, только мера роста общая с вердиктом.

Живёт в `classify`, а не в `collect`, потому что знает про пороги: контракт
слоёв запрещает сбору знать про классификацию, и правильно — сбор обязан
оставаться бесплатным в тестах.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.rulesets import active_ruleset
from ahrefs_cases.classify.verdicts import evaluate
from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models.project import Project

logger = logging.getLogger(__name__)

_WORTH_PAYING = (Group.GOOD, Group.MEDIUM)
"""Группы, за которые имеет смысл доплачивать.

`insufficient_data` сюда не входит намеренно: покупать подтверждающие метрики
там, где не хватило даже трафика, — значит платить за заведомо неполный кейс.
`poor` тем более: диагностика «плохих» (Ф3в) считается по уже купленному.
"""


async def stage2_candidates(
    session: AsyncSession,
    projects: Sequence[Project],
    *,
    source: MetricSource,
) -> list[int]:
    """Проекты, которым стоит купить дорогие метрики шага 2.

    Вердикт здесь считается по данным шага 1, и `good` в нём недостижим по
    построению — подтверждающих метрик ещё нет. Это не мешает: `good` и
    `medium` различаются как раз ими, а для решения «платить или нет» хватает
    того, что проект не «плохой».
    """
    if not projects:
        return []

    ruleset = await active_ruleset(session)
    chosen = [
        item.project.id
        for item in await evaluate(session, projects, ruleset, source=source)
        if item.computed.decision.group in _WORTH_PAYING
    ]
    logger.info(
        "stage2_candidates",
        extra={
            "considered": len(projects),
            "selected": len(chosen),
            "ruleset": ruleset.version,
        },
    )
    return chosen
