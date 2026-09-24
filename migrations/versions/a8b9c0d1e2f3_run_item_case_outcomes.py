"""исходы сборки кейсов в журнале прогона: «не положен по группе» и остальные

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-24 23:30:00.000000

Ступень кейсов писала в журнал только строку прогона: «собрано 0, пропущено
53» при десяти собранных кейсах и ни одной судьбы (Z46). Судьба проекта в
сборке — не исход сбора: «не положен по группе» нельзя записать ни как «нет
данных», ни как «строка не принята» — слово исхода на экране берётся из
значения. Собранный кейс — прежний `OK`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседние миграции).
revision: str = "a8b9c0d1e2f3"  # pragma: allowlist secret
down_revision: str | None = "f7a8b9c0d1e2"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM = "run_item_outcome"
_VALUES = (
    "CASE_NOT_ELIGIBLE",
    "CASE_INSUFFICIENT_DATA",
    "CASE_NO_VERDICT",
    "CASE_VERDICT_MISMATCH",
    "CASE_BLOCKED",
)
"""Имена членов `RunItemOutcome`, а не значения: `sa.Enum` хранит в Postgres
имена (урок L12), и значение в нижнем регистре прошло бы миграцию зелёным, а
упала бы первая вставка."""


def upgrade() -> None:
    """`ADD VALUE` вне транзакции — как у `SKIPPED_ABORTED` (7b21c4e9d0a3)."""
    with op.get_context().autocommit_block():
        for value in _VALUES:
            op.execute(f"ALTER TYPE {_ENUM} ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Значение enum в Postgres не удаляется: `DROP VALUE` не существует, а строки
    журнала с этими исходами при откате остались бы нечитаемыми. Осознанный no-op.
    """
