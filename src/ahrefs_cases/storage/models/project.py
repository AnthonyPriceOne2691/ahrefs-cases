"""Проект — центр домена: домен клиента и период работ по нему."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import ProjectStatus, TargetMode
from ahrefs_cases.storage.models._base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """Все поля входного файла обязательны по ТЗ, кроме объёма работ и заметок.

    `period_end` заполняем всегда, даже если работы продолжаются: точку Б задаёт
    агентство, а не «сегодня» — иначе кейс меняется от даты пересборки.
    """

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("domain", "target_mode", "period_start", name="uq_project_domain_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    """Канонический хост: без схемы, без www, punycode → ascii."""

    target_mode: Mapped[TargetMode] = mapped_column(
        Enum(TargetMode, name="target_mode"), nullable=False, default=TargetMode.SUBDOMAINS
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    niche: Mapped[str] = mapped_column(String(120), nullable=False)
    geo: Mapped[str] = mapped_column(String(2), nullable=False)
    """ISO 3166-1 alpha-2 основной страны проекта: гео-разрез берём из файла."""

    service_type: Mapped[str] = mapped_column(String(120), nullable=False)
    client: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    publishable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    """Разрешение назвать клиента. `False` → кейс анонимный, домен не появляется
    ни в тексте, ни в имени файла."""

    work_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Например число построенных ссылок. По ТЗ необязательно: при пустом
    значении блок «что сделали» в кейсе скрывается, а не выдумывается."""

    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"), nullable=False, default=ProjectStatus.NEW
    )
