"""удалённая учётка остаётся ради журнала прогонов

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-14 21:20:00.000000

Удаления пользователя не было, и это было решением: `runs.started_by` стоит с
`ON DELETE RESTRICT`, а журнал отвечает на вопрос «кто это запускал» — ответ
обязан переживать увольнение.

Поле решает противоречие между «удалить» и «сохранить историю»: учётка с
прогонами помечается удалённой и пропадает из списка, но строка остаётся, и
журнал по-прежнему называет человека — с пометкой «(удалён)». Учётка без
прогонов удаляется по-настоящему: терять нечего, а почта освобождается.

Поле допускает `NULL`, и это не забывчивость: `NULL` здесь — «живая учётка»,
то есть состояние всех существующих строк. Умолчания не нужно.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседнюю миграцию).
revision: str = "f7a8b9c0d1e2"  # pragma: allowlist secret
down_revision: str | None = "e6f7a8b9c0d1"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "users"
_COLUMN = "deleted_at"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
