"""Пользователь и его группа доступа."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import UserGroup
from ahrefs_cases.storage.models._base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    group: Mapped[UserGroup] = mapped_column(
        Enum(UserGroup, name="user_group"), nullable=False, default=UserGroup.USER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    permissions: Mapped[dict[str, bool]] = mapped_column(JSONB, nullable=False, default=dict)
    """Личные права поверх группы: `{"edit_thresholds": true}` даёт право, а
    `false` — отбирает, даже если группа его даёт.

    Приём перенесён из CRM агентства, где эта развилка уже пройдена: права
    расходятся быстрее, чем роли, и первое же новое право иначе требует либо
    четвёртой группы, либо правки кода. Здесь выдача права одному человеку —
    запись в этом поле.
    """

    # Прав у модели нет намеренно: право — строка, а таблица «группа → права»
    # живёт одна, в `api/deps.py`. Свойства `can_*` стояли здесь с Ф1, ими не
    # пользовался никто, и это худший вид дубля — он не расходится ровно до
    # первой ссылки на него (урок L33).
