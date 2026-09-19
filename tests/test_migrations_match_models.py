"""Цепочка миграций и модели обязаны сходиться.

Модели описывают, какую схему хочет видеть код. Миграции — единственный
способ, которым схема появляется в проде. Разойтись они могут молча: поле
добавили в модель и забыли миграцию, а `migrated_db` этого не заметит —
`upgrade head` на применённой схеме это no-op, и расхождение доживёт до
развёртывания на чистой базе.

Проверка спрашивает у alembic, что бы он дописал поверх текущей схемы.
Пусто — значит цепочка доезжает ровно до того, что ждёт код.
"""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Column, Connection, Integer, MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.storage.models import Base

#: Служебная таблица alembic: в моделях её нет и быть не должно.
_IGNORED_TABLES = frozenset({"alembic_version"})


def _touches_ignored_table(diff: object) -> bool:
    parts = diff if isinstance(diff, tuple) else (diff,)
    return any(isinstance(p, str) and p in _IGNORED_TABLES for p in parts)


def _diff(connection: Connection, metadata: MetaData) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={"compare_type": True, "compare_server_default": True},
    )
    return [d for d in compare_metadata(context, metadata) if not _touches_ignored_table(d)]


async def _collect(session: AsyncSession, metadata: MetaData) -> list[object]:
    connection = await session.connection()
    return await connection.run_sync(lambda sync_conn: _diff(sync_conn, metadata))


async def test_migrations_produce_exactly_the_schema_models_expect(
    db_session: AsyncSession,
) -> None:
    diffs = await _collect(db_session, Base.metadata)
    assert not diffs, (
        "схема после `alembic upgrade head` расходится с моделями — нужна миграция.\n"
        "Alembic дописал бы:\n  " + "\n  ".join(repr(d) for d in diffs)
    )


async def test_the_check_itself_can_fail(db_session: AsyncSession) -> None:
    """Проверка, способная только проходить, ничего не доказывает."""
    probe = MetaData()
    Table("таблица_которой_нет", probe, Column("id", Integer, primary_key=True))
    assert await _collect(db_session, probe), "сравнение не увидело лишнюю таблицу"
