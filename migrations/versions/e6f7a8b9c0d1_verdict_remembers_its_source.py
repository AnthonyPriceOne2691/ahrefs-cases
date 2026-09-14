"""вердикт помнит, по каким рядам он посчитан

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-14 11:10:00.000000

Числа таблицы кейса берутся из вердикта, кривые — из серий. Пока вердикт не
помнил источник, совпадение этих двух миров держалось на дисциплине вызова: на
стенде, где по проекту лежат и живые, и фикстурные ряды, 14.09.2026 в один PDF
попали таблица «35 394 → 60 101» и кривая, кончающаяся на 1 058 129.

Поле добавляется **допускающим NULL**, и это не забывчивость. Существующие
вердикты посчитаны по разным источникам: часть — по фикстурам разработки, часть
— по живым рядам калибровочного прогона. Проставить им одно значение значило бы
записать в базу неправду ровно там, где её убирают; NULL здесь читается как
«источник неизвестен», и кейс по такому вердикту не собирается, пока его не
пересчитают (`classify` бесплатен и в Ahrefs не ходит).

Удалять старые вердикты тоже нельзя: `cases.verdict_id` стоит с
`ON DELETE RESTRICT`, и на стенде с собранными кейсами миграция упала бы — а
запись о выданном клиенту артефакте важнее стройности схемы.

Тип `metric_source` уже существует (его создала начальная схема под
`metric_points`), поэтому `create_type=False`: повторный `CREATE TYPE` уронил бы
миграцию. Значения в базе — **имена** членов enum (`LIVE`, `FIXTURE`, `MANUAL`),
а не их значения: `sa.Enum(MetricSource)` хранит `.name` (урок L12).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседнюю миграцию).
revision: str = "e6f7a8b9c0d1"  # pragma: allowlist secret
down_revision: str | None = "d5e6f7a8b9c0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "verdicts"
_COLUMN = "source"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            postgresql.ENUM("LIVE", "FIXTURE", "MANUAL", name="metric_source", create_type=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
