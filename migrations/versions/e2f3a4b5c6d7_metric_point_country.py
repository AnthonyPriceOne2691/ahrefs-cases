"""купленные ряды помнят страну: `metric_points.country`

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-07 23:30:00.000000

Z53: точка различалась проектом, метрикой, месяцем и источником — страны среди них
не было. Месяцы кампании сайта по US переходили его кампании по DE, а после смены
первой страны цифры оставались по прежней, и никто этого не видел. Решение владельца
07.10.2026 — не докупать, а предупреждать; для предупреждения точка обязана помнить,
по какой стране куплена. «Весь мир» — пустая строка: запрос к Ahrefs без фильтра.

Купленным точкам проставляется первая страна их проекта: до этой миграции сбор
покупал именно по ней (`storage.geo.ahrefs_country`), а смена страны у проекта с
рядами до сегодняшних списков стран (#45) была невозможна — гео был одним кодом.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседние миграции).
revision: str = "e2f3a4b5c6d7"  # pragma: allowlist secret
down_revision: str | None = "d1e2f3a4b5c6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "metric_points",
        sa.Column("country", sa.String(2), nullable=False, server_default=""),
    )
    op.execute(
        """
        UPDATE metric_points AS point
        SET country = CASE
            WHEN project.geo IN ('', 'WW') THEN ''
            ELSE split_part(project.geo, ',', 1)
        END
        FROM projects AS project
        WHERE project.id = point.project_id
        """
    )


def downgrade() -> None:
    op.drop_column("metric_points", "country")
