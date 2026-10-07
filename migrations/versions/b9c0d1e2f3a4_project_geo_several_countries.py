"""гео проекта: несколько стран через запятую или весь мир

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-10-07 18:00:00.000000

Команда агентства 07.10.2026: бывают проекты на несколько стран и на весь мир —
«DE, AT, CH» и «Worldwide». Колонка из двух букв их не вмещает; канон и разбор —
`storage.geo`. Прежние значения (одна страна) остаются каноном как есть.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседние миграции).
revision: str = "b9c0d1e2f3a4"  # pragma: allowlist secret
down_revision: str | None = "a8b9c0d1e2f3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "projects", "geo", type_=sa.String(255), existing_type=sa.String(2), existing_nullable=False
    )


def downgrade() -> None:
    """Обратно в две буквы — по тому же правилу, по которому считает сбор.

    Несколько стран → первая (по ней Ahrefs и считал цифры); весь мир → пусто:
    прежний код запрашивал Ahrefs без страны ровно тогда, когда гео пустое.
    """
    op.execute(
        "UPDATE projects SET geo = CASE WHEN geo = 'WW' THEN '' "
        "ELSE split_part(geo, ',', 1) END WHERE length(geo) > 2 OR geo = 'WW'"
    )
    op.alter_column(
        "projects", "geo", type_=sa.String(2), existing_type=sa.String(255), existing_nullable=False
    )
