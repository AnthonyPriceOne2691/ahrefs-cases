"""Пользователь и его группа доступа."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
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

    @property
    def can_edit_thresholds(self) -> bool:
        """Право строкой, а не сравнением роли по месту вызова.

        Проверка живёт здесь, чтобы «кто может править пороги» имело один ответ:
        разъехавшиеся копии условия — способ тихо сдвинуть границу без ревью.
        """
        return self.group in (UserGroup.ENGINEER, UserGroup.ADMIN)

    @property
    def can_manage_users(self) -> bool:
        return self.group in (UserGroup.ENGINEER, UserGroup.ADMIN)

    @property
    def can_change_technical_settings(self) -> bool:
        """Ключи, лимиты расхода, провайдер — работа инженера, не руководителя."""
        return self.group is UserGroup.ENGINEER
