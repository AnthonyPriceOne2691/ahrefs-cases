"""Уборка за тестом: удаляются **свои** строки, а не таблицы целиком.

Почему это отдельный модуль, а не четыре одинаковых функции по месту: приём
разошёлся копированием — он был в тестах чтения, оттуда попал в прогоны, пороги
и приём списка. Пятая копия появилась бы при следующем тесте с базой.

Почему по владению, а не `delete(Model)`: дев-база **общая и живёт между
прогонами**. На ней смотрят экраны, собирают данные руками, готовят показ.
Очистка таблицы уносит эту работу, и тест при этом зелёный — он ведь убрал за
собой. Найдено показом: карточка сказала «не классифицирован» про проект,
который часом раньше был «хорошим» (урок L79).

Изоляцию откатом транзакции здесь применить нельзя: приложение ходит своими
соединениями, и его записи откат тестовой транзакции не видит (урок L68).
Значит уборка нужна — и обязана быть точной.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.units_ledger import UnitsLedger
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict


async def delete_owned(
    session: AsyncSession,
    *,
    domains: Sequence[str] = (),
    emails: Sequence[str] = (),
) -> None:
    """Удалить строки, принадлежащие проектам `domains` и людям `emails`.

    Порядок — от детей к родителям: артефакты и кейсы, вердикты и точки, потом
    сами проекты; прогоны и их расход — по своему пользователю, потом он сам.

    Прогон, открытый системным пользователем, не удаляется: он тесту не
    принадлежит, даже если случился во время его работы.
    """
    if domains:
        project_ids = list(
            (await session.execute(select(Project.id).where(Project.domain.in_(domains))))
            .scalars()
            .all()
        )
        if project_ids:
            case_ids = list(
                (await session.execute(select(Case.id).where(Case.project_id.in_(project_ids))))
                .scalars()
                .all()
            )
            if case_ids:
                await session.execute(
                    delete(CaseArtifact).where(CaseArtifact.case_id.in_(case_ids))
                )
            await session.execute(delete(Case).where(Case.project_id.in_(project_ids)))
            await session.execute(delete(Verdict).where(Verdict.project_id.in_(project_ids)))
            await session.execute(
                delete(MetricPoint).where(MetricPoint.project_id.in_(project_ids))
            )
        await session.execute(delete(Project).where(Project.domain.in_(domains)))

    if emails:
        user_ids = list(
            (await session.execute(select(User.id).where(User.email.in_(emails)))).scalars().all()
        )
        if user_ids:
            run_ids = list(
                (await session.execute(select(Run.id).where(Run.started_by.in_(user_ids))))
                .scalars()
                .all()
            )
            if run_ids:
                await session.execute(delete(UnitsLedger).where(UnitsLedger.run_id.in_(run_ids)))
                await session.execute(delete(Run).where(Run.id.in_(run_ids)))
        await session.execute(delete(User).where(User.email.in_(emails)))
