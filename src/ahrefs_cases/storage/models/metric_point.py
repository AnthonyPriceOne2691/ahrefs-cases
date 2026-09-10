"""Точка серии метрики — сырые данные, за которые заплачено."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models._base import Base


class MetricPoint(Base):
    """Одна строка = одна метрика одного проекта на одну дату.

    Уникальность по `(project_id, metric, date, source)` — не гигиена, а деньги:
    повторный сбор обновляет точку, а не покупает её заново. На этом инварианте
    держится вся экономия units (docs/UNITS_ECONOMY.md).
    """

    __tablename__ = "metric_points"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "metric", "point_date", "source", name="uq_metric_point_identity"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric: Mapped[Metric] = mapped_column(Enum(Metric, name="metric"), nullable=False)
    point_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[MetricSource] = mapped_column(
        Enum(MetricSource, name="metric_source"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
