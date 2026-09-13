"""действующая версия порогов — ровно одна

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-13 22:40:00.000000

Инвариант был, но держался дисциплиной: `recalc.activate` выключает все версии
и включает одну. Любой другой путь — правка флага вручную, тест, наполовину
прошедшая транзакция — оставляет две активные, и сервис молча берёт **новейшую**
(`active_ruleset` сортирует по id). Вердикты при этом считаются по версии,
которую никто не утверждал.

Найдено 13.09.2026 на стенде: после прогона тестов активными оказались сразу
`0.0.0-default` и `0.1.0-проверка`. Частичный уникальный индекс делает такое
состояние невозможным, а не маловероятным.

Перед созданием индекса лишние активные версии гасятся: остаётся та, что и так
действовала по правилу выбора — новейшая по id. Миграция, падающая на данных,
которые сама же и должна привести в порядок, бесполезна.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# Идентификаторы ревизий alembic — имена, а не секреты (см. соседнюю миграцию).
revision: str = "d5e6f7a8b9c0"  # pragma: allowlist secret
down_revision: str | None = "c4d5e6f7a8b9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "uq_ruleset_single_active"


def upgrade() -> None:
    op.execute(
        """
        UPDATE rulesets
           SET is_active = false
         WHERE is_active
           AND id <> (SELECT max(id) FROM rulesets WHERE is_active)
        """
    )
    op.execute(f"CREATE UNIQUE INDEX {_INDEX} ON rulesets ((is_active)) WHERE is_active")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
