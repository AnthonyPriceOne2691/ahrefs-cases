"""Пользователь и его группа доступа."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, text
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

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    """Когда учётку удалили. `NULL` — живая.

    Строка остаётся, потому что на неё ссылается журнал прогонов
    (`runs.started_by`), а журнал отвечает на вопрос «кто это запускал» — и
    ответ обязан переживать увольнение. Удалённый человек исчезает из списка,
    войти не может, а в журнале остаётся с пометкой «(удалён)».

    Учётка, за которой не числится ни одного прогона, удаляется по-настоящему:
    терять нечего, а почта освобождается для повторного заведения."""

    permissions: Mapped[dict[str, bool]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        # Умолчание стоит и в базе: миграция обязана была его поставить,
        # чтобы `nullable=False` пережил существующие строки, и снимать
        # его незачем — вставка мимо ORM тоже не должна ронять таблицу.
        # Модель обязана говорить о схеме правду, иначе сверка моделей
        # с миграциями краснеет на пустом месте и её снимут.
        server_default=text("'{}'::jsonb"),
    )
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
