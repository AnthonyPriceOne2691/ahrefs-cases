"""Скриншот проекта: экран отчёта Ahrefs или видимости в ИИ, загруженный специалистом."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage.models._base import Base, TimestampMixin

SCREENSHOT_KINDS = ("ahrefs", "ai")
"""Отчёт Ahrefs или экран видимости бренда в ChatGPT, Perplexity, AI Overviews."""


class ProjectScreenshot(Base, TimestampMixin):
    """Файл лежит на диске (`storage.screenshots`), здесь — где и что это.

    Строка уходит вместе с проектом каскадом, файл стирает удаление проекта
    после коммита. Один и тот же скрин дважды не принимается: та же картинка
    в брифе дважды — шум, а не второй довод.
    """

    __tablename__ = "project_screenshots"
    __table_args__ = (
        UniqueConstraint("project_id", "checksum", name="uq_screenshot_once_per_project"),
        CheckConstraint("kind IN ('ahrefs', 'ai')", name="ck_screenshot_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    caption: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    """Путь файла внутри каталога скриншотов: `<проект>/<uuid>.png`. Имя файла
    человека на диск не попадает."""

    mime: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    """Кто загрузил. `SET NULL`: удаление учётки без прогонов — настоящее, и
    `RESTRICT` его бы сломал."""
