"""строка журнала помнит номер проекта и после его удаления: `run_items.project_ref`

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-08 15:00:00.000000

Z41: удаление проекта обнуляет `run_items.project_id` (`ON DELETE SET NULL`), и журнал
различал удалённые проекты прогона только доменом — две удалённые кампании одного сайта
сливались в одну судьбу с суммой units (на копии дев-базы `nordvpn.com` — «ok, 264» вместо
двух по 132). Номер без внешнего ключа удаление переживает.

Строкам, у которых проект ещё есть, номер проставляется из `project_id`; у строк уже
удалённых проектов его не вернуть — для них остаётся прежнее различение по домену.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседние миграции).
revision: str = "f3a4b5c6d7e8"  # pragma: allowlist secret
down_revision: str | None = "e2f3a4b5c6d7"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run_items", sa.Column("project_ref", sa.Integer(), nullable=True))
    op.execute("UPDATE run_items SET project_ref = project_id WHERE project_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("run_items", "project_ref")
