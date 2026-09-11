"""Заведение пользователей из командной строки.

Первый пользователь должен откуда-то взяться: экрана управления людьми нет, а
войти в сервис без учётной записи нельзя. Команда — это и есть ответ, и она
же остаётся рабочей, пока список сотрудников от заказчика не придёт.

Пароль спрашивается, а не передаётся аргументом: аргумент остаётся в истории
шелла и виден в списке процессов любому на машине.
"""

from __future__ import annotations

import getpass
import sys

from sqlalchemy import select

from ahrefs_cases.api.security import generate_password, hash_password
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.session import get_sessionmaker

EXIT_BAD_INPUT = 2
MIN_PASSWORD_LEN = 10
"""Длина, а не «сложность»: правило про заглавные и цифры даёт `Password1!`
у всех шестерых сотрудников, а длина хотя бы измерима."""


async def add_user(email: str, group: str, *, password: str | None = None) -> int:
    """Завести пользователя. Пароль спрашивается, если не передан явно (тесты)."""
    try:
        user_group = UserGroup(group)
    except ValueError:
        known = ", ".join(item.value for item in UserGroup)
        print(f"неизвестная группа {group!r}. Известные: {known}", file=sys.stderr)
        return EXIT_BAD_INPUT

    secret = password if password is not None else _ask_password()
    if secret is None:
        return EXIT_BAD_INPUT
    generated = not secret
    if generated:
        # Пустой ввод — просьба сгенерировать: первый администратор заводится
        # на сервере, и придумывать пароль в чужой консоли незачем.
        secret = generate_password()

    async with get_sessionmaker()() as session:
        existing = (
            (await session.execute(select(User).where(User.email == email))).scalars().first()
        )
        if existing is not None:
            print(
                f"пользователь {email} уже заведён: группа {existing.group.value}", file=sys.stderr
            )
            return EXIT_BAD_INPUT
        session.add(
            User(
                email=email,
                full_name="",
                password_hash=hash_password(secret),
                group=user_group,
                is_active=True,
            )
        )
        await session.commit()
    print(f"заведён {email}, группа {user_group.value}")
    if generated:
        print(f"пароль (показывается один раз): {secret}")
    return 0


def _ask_password() -> str | None:
    """Спросить пароль дважды. Пустой ввод означает «сгенерируй сам».

    Несовпадение — отказ, а не третья попытка молча.
    """
    first = getpass.getpass("пароль (пусто — сгенерировать): ")
    if not first:
        return ""
    if len(first) < MIN_PASSWORD_LEN:
        print(f"пароль короче {MIN_PASSWORD_LEN} символов", file=sys.stderr)
        return None
    if first != getpass.getpass("ещё раз: "):
        print("пароли не совпали", file=sys.stderr)
        return None
    return first
