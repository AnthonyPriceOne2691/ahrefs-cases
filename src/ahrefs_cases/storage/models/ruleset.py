"""Версионированные пороги классификации."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage.models._base import Base, TimestampMixin


class Ruleset(Base, TimestampMixin):
    """Сохранение из интерфейса создаёт **новую версию**, а не правит текущую.

    Вердикты привязаны к версии и обязаны оставаться объяснимыми: без версии на
    вопрос «почему тут medium» через месяц ответить нечем. Активна одна версия.
    """

    __tablename__ = "rulesets"
    __table_args__ = (UniqueConstraint("version", name="uq_ruleset_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    """Зачем меняли: «подняли порог трафика после калибровки на 80 доменах».
    Без причины история версий превращается в список дат."""
