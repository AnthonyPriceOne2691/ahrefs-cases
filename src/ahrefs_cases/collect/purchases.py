"""Что по домену покупали у Ahrefs — по журналу расхода units.

Отдельной записи «метрика куплена» в базе нет, и заводить её задним числом
поздно: прогоны уже прошли. Зато есть журнал расхода (`units_ledger`), где на
каждый ответ провайдера стоит строка с endpoint'ом и доменом, — и он отвечает
ровно на нужный вопрос: платили за эту метрику или нет.

Разница не косметическая (Z25). Прочерк в карточке означал два разных случая:
**не покупали** — сознательная экономия воронки, шаг 2 платится только
кандидатам в кейсы; **купили, а Ahrefs ничего не отдал** — данных нет и не
будет. Заказчик спрашивает «вы не купили или не смогли?», и разница эта в
деньгах: в первом случае докупить можно, во втором докупать нечего.
"""

from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.collect.endpoints import ALL_SPECS
from ahrefs_cases.storage._enums import LedgerKind, Metric
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import RunItem
from ahrefs_cases.storage.models.units_ledger import UnitsLedger

_METRICS_BY_ENDPOINT = {spec.name: frozenset(spec.metrics.values()) for spec in ALL_SPECS}
"""Endpoint → метрики, которые он отдаёт. Берётся у спек, а не переписывается:
второй экземпляр разошёлся бы с первым при добавлении endpoint'а."""


async def bought_metrics(session: AsyncSession, domain: str) -> frozenset[Metric] | None:
    """Метрики, за которые по домену платили, — кроме покупок удалённых проектов.

    `None` — журнал про этот домен не знает ничего (ни одной строки расхода):
    так бывает у данных, собранных до появления журнала. Тогда честный ответ —
    «неизвестно», а не «не покупали»: пустое множество утверждало бы то, чего
    журнал не говорил.

    Журнал расхода удаление переживает, и проект, загруженный заново, до своего
    шага 2 получал подпись «нет у Ahrefs» по покупке удалённого (Z40). Покупка не
    считается, если её прогон знал этот домен только у удалённых проектов; был в
    прогоне живой проект домена — считается, как прежде. Домен журналу знаком, а
    всё куплено удалёнными — пустое множество: «не собирали».
    """
    dead = exists().where(
        RunItem.run_id == UnitsLedger.run_id,
        RunItem.project_id.is_(None),
        RunItem.raw_domain == UnitsLedger.target,
    )
    live = exists().where(
        RunItem.run_id == UnitsLedger.run_id,
        RunItem.project_id == Project.id,
        Project.domain == UnitsLedger.target,
    )
    rows = (
        await session.execute(
            select(UnitsLedger.endpoint, (live | ~dead).label("counts"))
            .where(UnitsLedger.target == domain, UnitsLedger.kind == LedgerKind.SPENT)
            .distinct()
        )
    ).all()
    if not any(name for name, _ in rows):
        return None
    return frozenset(
        metric
        for name, counts in rows
        if name and counts
        for metric in _METRICS_BY_ENDPOINT.get(name, frozenset())
    )
