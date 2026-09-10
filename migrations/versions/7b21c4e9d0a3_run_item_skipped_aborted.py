"""исход прогона `skipped_aborted`: задача не выполнялась из-за предохранителя

Revision ID: 7b21c4e9d0a3
Revises: 3459a03e3ba6
Create Date: 2026-09-10 20:05:00.000000

Почему отдельным значением, а не `failed`: по такому домену запрос **не
делался**. Слить их значило бы потерять различие между «Ahrefs ответил
ошибкой» и «мы не спрашивали» — а решать, повторять ли прогон, оператор будет
именно по нему.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# Идентификаторы ревизий alembic: hex-строки, которые detect-secrets принимает за
# ключ по энтропии. Это не секрет, а имя миграции — помечаем на строке, а не
# расширением baseline: baseline должен только сокращаться.
revision: str = "7b21c4e9d0a3"  # pragma: allowlist secret
down_revision: str | None = "3459a03e3ba6"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM = "run_item_outcome"
_VALUE = "SKIPPED_ABORTED"
"""Имя члена enum, а НЕ его значение.

`sa.Enum(RunItemOutcome)` по умолчанию хранит в базе `.name`, то есть
`SKIPPED_ABORTED`, тогда как `RunItemOutcome.SKIPPED_ABORTED.value` — это
`"skipped_aborted"`. Первая версия этой миграции добавила значение в нижнем
регистре: `ALTER TYPE` проходил, миграция была зелёной, а первая же вставка
упала бы в рантайме. Проверять надо `enum_range`, а не успех миграции.
"""


def upgrade() -> None:
    """`ALTER TYPE ... ADD VALUE` вне транзакции.

    Postgres не разрешает добавлять значение enum внутри транзакционного блока
    (до 12 — вовсе, после — с оговорками про использование в той же
    транзакции). Alembic по умолчанию оборачивает миграцию в транзакцию,
    поэтому нужен autocommit-блок; без него миграция падает не на нашей
    логике, а на попытке коммита.
    """
    with op.get_context().autocommit_block():
        op.execute(f"ALTER TYPE {_ENUM} ADD VALUE IF NOT EXISTS '{_VALUE}'")


def downgrade() -> None:
    """Значение enum в postgres не удаляется — и это не наша лень.

    `ALTER TYPE ... DROP VALUE` в postgres не существует: удаление означало бы
    пересоздание типа с перезаписью всех колонок, которые на нём стоят. Строки
    с этим исходом при откате остались бы нечитаемыми, поэтому downgrade —
    осознанный no-op, а не забытая реализация.
    """
