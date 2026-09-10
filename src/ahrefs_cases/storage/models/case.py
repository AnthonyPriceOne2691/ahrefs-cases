"""Кейс и его артефакты."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import ArtifactFormat, CaseStatus
from ahrefs_cases.storage.models._base import Base, TimestampMixin


class Case(Base, TimestampMixin):
    """Кейс собирается для групп good и medium.

    `anonymized` — поле кейса, а не решение на этапе рендера: анонимность влияет
    и на текст, и на графики, и на имя файла, поэтому решается один раз.
    """

    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    verdict_id: Mapped[int] = mapped_column(
        ForeignKey("verdicts.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    """Перегенерация с новыми данными через полгода-год — требование ТЗ, поэтому
    кейсы версионируются, а не перезаписываются."""

    template: Mapped[str] = mapped_column(String(80), nullable=False, default="default")
    anonymized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    highlights: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status"), nullable=False, default=CaseStatus.DRAFT
    )


class CaseArtifact(Base):
    """Файл кейса. Чек-сумма нужна, чтобы отличить «пересобрали» от «переименовали»."""

    __tablename__ = "case_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fmt: Mapped[ArtifactFormat] = mapped_column(
        Enum(ArtifactFormat, name="artifact_format"), nullable=False
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    """Итоговое имя: «домен + Кейс», либо «сайт в нише X + Кейс» для непубличных."""

    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
