"""Версии порогов в базе: сид, активная версия, чтение.

Пороги — единственное, что в этом сервисе правят люди без деплоя, и каждая
правка обязана быть версией: вердикт хранит `ruleset_id`, иначе через месяц на
вопрос «почему тут medium» ответить нечем.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.thresholds import Thresholds, ThresholdsError, load_seed, parse
from ahrefs_cases.storage.models.ruleset import Ruleset


async def seed_thresholds(session: AsyncSession, path: Path | None = None) -> Ruleset:
    """Записать пороги из файла как версию, если такой версии ещё нет.

    Идемпотентно **по версии**, а не по содержимому: если файл поправили, не
    сменив `version`, база остаётся прежней. Это не недосмотр — иначе сид
    молча переписывал бы пороги, по которым уже вынесены вердикты, и они
    перестали бы объясняться.
    """
    seed = load_seed(path)
    existing = await by_version(session, seed.version)
    if existing is not None:
        return existing

    ruleset = Ruleset(
        version=seed.version,
        payload=seed.model_dump(mode="json"),
        is_active=await _count(session) == 0,
        note="сид из config/thresholds.example.yml (Приложение А)",
    )
    session.add(ruleset)
    await session.flush()
    return ruleset


async def by_version(session: AsyncSession, version: str) -> Ruleset | None:
    stmt = select(Ruleset).where(Ruleset.version == version)
    return (await session.execute(stmt)).scalar_one_or_none()


async def active_ruleset(session: AsyncSession) -> Ruleset:
    """Действующая версия порогов.

    Отсутствие активной версии — ошибка, а не повод взять дефолты: вердикты по
    неутверждённым порогам выглядят как настоящие и расходятся с экспертной
    оценкой молча.
    """
    stmt = select(Ruleset).where(Ruleset.is_active.is_(True)).order_by(Ruleset.id.desc())
    ruleset = (await session.execute(stmt)).scalars().first()
    if ruleset is None:
        message = (
            "в базе нет активной версии порогов. Засейте её "
            "(`seed_thresholds`) — классифицировать по умолчаниям нельзя: "
            "эти пороги никто не утверждал."
        )
        raise ThresholdsError(message)
    return ruleset


def thresholds_of(ruleset: Ruleset) -> Thresholds:
    """Пороги версии как типы."""
    return parse(dict(ruleset.payload))


async def _count(session: AsyncSession) -> int:
    from sqlalchemy import func

    stmt = select(func.count()).select_from(Ruleset)
    return int((await session.execute(stmt)).scalar_one())
