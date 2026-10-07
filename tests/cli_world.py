"""Свой мир теста команд консоли в общей дев-базе.

Команды консоли ходят своими сессиями и видят только закоммиченное. Поэтому их тесты
пишут строки коммитом, а не в откатываемой транзакции `db_session`: её `TRUNCATE`
держал бы команду на замках таблиц до конца теста, а тест ждал бы команду. И сами за
собой убирают: прогоны, открытые за время теста, свои проекты и людей, свою версию
порогов — вернув стенду его действующую (уроки L51, L54, Z12).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

from sqlalchemy import delete, func, select
from tests.owned_rows import (
    active_versions,
    delete_owned,
    drop_ruleset,
    own_active_ruleset,
    restore_active,
)

from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.session import get_sessionmaker


@asynccontextmanager
async def own_world(
    *, ruleset: str, domains: Sequence[str] = (), emails: Sequence[str] = ()
) -> AsyncIterator[None]:
    """Своя действующая версия порогов на время теста; после — ничего своего в базе.

    Своя версия нужна каждому тесту, который классифицирует: сбор и `classify`
    переписывают вердикты **всех** проектов базы по действующей версии, и по чужой тест
    переписал бы вердикты стенда (Z12).
    """
    async with get_sessionmaker()() as session:
        last_run = int(await session.scalar(select(func.max(Run.id))) or 0)
        stand = [one for one in await active_versions(session) if one != ruleset]
        await delete_owned(session, domains=domains, emails=emails)
        await drop_ruleset(session, ruleset)
        await own_active_ruleset(session, ruleset)
        await session.commit()
    try:
        yield
    finally:
        async with get_sessionmaker()() as session:
            await session.execute(delete(Run).where(Run.id > last_run))
            await delete_owned(session, domains=domains, emails=emails)
            await restore_active(session, stand)
            await drop_ruleset(session, ruleset)
            await session.commit()
