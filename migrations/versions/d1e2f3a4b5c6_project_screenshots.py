"""скриншоты проекта: экраны Ahrefs и видимости в ИИ для брифа

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-10-07 23:00:00.000000

Команда агентства 07.10.2026: скрины Ahrefs — полуавтомат, специалист снимает
экран по ссылке из брифа и загружает его в карточку проекта, а скрин попадает в
PDF. Файл лежит на диске (`storage.screenshots`), здесь — строка о нём. Вид —
строкой с проверкой, а не типом ENUM: тип пришлось бы удалять в откате руками
(урок L5).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседние миграции).
revision: str = "d1e2f3a4b5c6"  # pragma: allowlist secret
down_revision: str | None = "c0d1e2f3a4b5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_screenshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("caption", sa.String(300), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("mime", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "checksum", name="uq_screenshot_once_per_project"),
        sa.CheckConstraint("kind IN ('ahrefs', 'ai')", name="ck_screenshot_kind"),
    )
    op.create_index("ix_project_screenshots_project_id", "project_screenshots", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_screenshots_project_id", table_name="project_screenshots")
    op.drop_table("project_screenshots")
