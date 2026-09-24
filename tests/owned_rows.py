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

from collections.abc import Callable, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
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


async def active_versions(session: AsyncSession) -> list[str]:
    """Какие версии порогов действуют сейчас — до вмешательства теста.

    Живёт рядом с уборкой по той же причине: дев-база **общая и живёт между
    прогонами**. Активная версия — чужая строка, которую тест не создавал и
    удалить не может, поэтому «убери свои строки» её не покрывает. Найдено
    13.09.2026: на стенде активировали `0.1.0-проверка`, прогон тестов оставил
    активной `0.0.0-default`, и пересчёт «по действующей» считал не то.
    """
    stmt = select(Ruleset.version).where(Ruleset.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def restore_active(session: AsyncSession, versions: Sequence[str]) -> None:
    """Вернуть стенду его действующую версию. Пустой список — возвращать нечего."""
    if not versions:
        return
    await make_active(session, versions[0])


async def make_active(session: AsyncSession, version: str) -> None:
    """Сделать версию действующей — единственной.

    Нужна тем тестам, которые проверяют **карточку**: вердикт ищется по
    действующей версии, и если на стенде активна чужая, тест находит
    `verdict: null` и падает `TypeError` — по причине окружения, а не кода.

    Порядок обязателен: сначала погасить все, потом зажечь одну. Инвариант
    держит частичный уникальный индекс `uq_ruleset_single_active`, он
    проверяется на каждом statement'е и отложенным быть не может — присвоение
    флага объекту оставило бы порядок записи на усмотрение ORM.
    """
    await session.execute(
        update(Ruleset).where(Ruleset.is_active.is_(True)).values(is_active=False)
    )
    await session.flush()
    await session.execute(update(Ruleset).where(Ruleset.version == version).values(is_active=True))
    await session.flush()


async def own_active_ruleset(session: AsyncSession, version: str) -> None:
    """Своя версия порогов теста — единственная действующая.

    Нужна каждому тесту, который запускает прогон сбора: с B6 прогон
    классифицирует **все** проекты базы по действующей версии, а в общей базе
    лежат проекты стенда с вердиктами по живым рядам. По чужой действующей
    версии тест переписал бы их источник на фикстурный — ровно то, что ловит
    сторож `stand_verdicts_survive_the_suite` (Z12). По своей версии тест пишет
    новые строки, которые сам же и уберёт `drop_ruleset`.
    """
    from ahrefs_cases.classify.thresholds import load_seed

    payload = {**load_seed().model_dump(mode="json"), "version": version}
    session.add(Ruleset(version=version, payload=payload, is_active=False, note="версия теста"))
    await session.flush()
    await make_active(session, version)


async def drop_ruleset(session: AsyncSession, version: str) -> None:
    """Убрать версию теста со всем, что под ней записано: кейсы, вердикты, её саму.

    От детей к родителям: кейс держит вердикт, вердикт — версию. Действующей
    версию до вызова должен сделать другой — иначе стенд останется без порогов.
    """
    ruleset_id = await session.scalar(select(Ruleset.id).where(Ruleset.version == version))
    if ruleset_id is None:
        return
    verdict_ids = select(Verdict.id).where(Verdict.ruleset_id == ruleset_id)
    case_ids = select(Case.id).where(Case.verdict_id.in_(verdict_ids))
    await session.execute(delete(CaseArtifact).where(CaseArtifact.case_id.in_(case_ids)))
    await session.execute(delete(Case).where(Case.verdict_id.in_(verdict_ids)))
    await session.execute(delete(Verdict).where(Verdict.ruleset_id == ruleset_id))
    await session.execute(delete(Ruleset).where(Ruleset.id == ruleset_id))


def isolated_ruleset(
    write: Callable[[Callable[..., object]], None], version: str
) -> Callable[[], None]:
    """Сделать свою версию единственной действующей; вернуть уборку.

    Уборка возвращает стенду его действующую версию и только потом сносит свою:
    иначе между шагами база осталась бы без действующих порогов. Остаток своей
    версии от упавшего прошлого прогона сносится до начала — и в «помнить, что
    было активно» не попадает.
    """
    stand: list[str] = []

    async def _setup(session: AsyncSession) -> None:
        found = await active_versions(session)
        stand.extend(item for item in found if item != version)
        await drop_ruleset(session, version)
        await own_active_ruleset(session, version)

    write(_setup)

    def undo() -> None:
        async def _teardown(session: AsyncSession) -> None:
            await restore_active(session, stand)
            await drop_ruleset(session, version)

        write(_teardown)

    return undo
