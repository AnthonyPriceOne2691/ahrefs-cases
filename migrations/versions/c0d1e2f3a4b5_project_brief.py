"""бриф копирайтеру: поля шаблона кейса у проекта

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-10-07 21:00:00.000000

Команда агентства 07.10.2026: PDF — бриф для копирайтера по шаблону кейса, и
половину его пунктов знает только специалист. Поля и списки значений описаны в
`storage.brief`; здесь — JSONB, а не колонка на поле: шаблон и списки правят
строкой в коде, а миграция на каждую правку списка была бы ценой без пользы
(тот же довод, что у `users.permissions`).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседние миграции).
revision: str = "c0d1e2f3a4b5"  # pragma: allowlist secret
down_revision: str | None = "b9c0d1e2f3a4"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "brief",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "brief")
