"""личные права пользователя поверх группы

Revision ID: c4d5e6f7a8b9
Revises: 7b21c4e9d0a3
Create Date: 2026-09-11 14:40:00.000000

Права расходятся быстрее, чем роли: первое же новое право иначе требует либо
новой группы, либо правки кода. Поле — JSONB, а не enum: значения приходят
списком известных прав, и `sa.Enum` пришлось бы менять миграцией на каждое
новое (а он ещё и хранит имена членов, а не значения — урок L12).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседнюю миграцию).
revision: str = "c4d5e6f7a8b9"  # pragma: allowlist secret
down_revision: str | None = "7b21c4e9d0a3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "users"
_COLUMN = "permissions"


def upgrade() -> None:
    """Добавить поле с умолчанием, чтобы существующие строки остались валидными."""
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Откат обязан работать: `upgrade → downgrade → upgrade` прогоняется в CI."""
    op.drop_column(_TABLE, _COLUMN)
