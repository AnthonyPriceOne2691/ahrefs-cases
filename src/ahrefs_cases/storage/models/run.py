"""Прогон сбора и судьба каждого проекта в нём."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import RunItemOutcome, RunStatus
from ahrefs_cases.storage.models._base import Base, TimestampMixin


class Run(Base, TimestampMixin):
    """Сбор — платная и падающая операция.

    Без журнала прогонов нельзя ни объяснить счёт за units, ни докрутить упавшие
    проекты, ни доверять цифрам в кейсе.
    """

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.QUEUED
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    projects_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    projects_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    projects_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    units_estimated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    units_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    params_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    """Группировка, набор метрик, версия клиента, провайдер. Без снимка нельзя
    сказать, чем считали прогон полугодовой давности."""

    error: Mapped[str] = mapped_column(Text, nullable=False, default="")


class RunItem(Base):
    """Что случилось с одним проектом в одном прогоне.

    Пропуск с причиной — штатный исход, а не ошибка: домен без данных, молодой
    домен, нехватка квоты. Прогон продолжается, причина остаётся в отчёте.
    """

    __tablename__ = "run_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    raw_domain: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    """Строка как пришла из файла: нужна, чтобы объяснить забракованные строки."""

    outcome: Mapped[RunItemOutcome] = mapped_column(
        Enum(RunItemOutcome, name="run_item_outcome"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    units_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
