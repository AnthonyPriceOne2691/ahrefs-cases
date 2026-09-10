"""Зависимости FastAPI: сессия и права.

Право — строка, роль — набор прав. Проверка стоит зависимостью на роутере, а не
условием внутри обработчика: иначе «кто может править пороги» расползается по
коду копиями, и граница сдвигается без ревью.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.storage import UserGroup, session_scope


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in session_scope():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Права как строки; роль — набор. Добавить право группе = правка этой таблицы,
# а не поиск сравнений с ролью по всему коду.
_GROUP_RIGHTS: dict[UserGroup, frozenset[str]] = {
    UserGroup.ENGINEER: frozenset(
        {"run", "read", "edit_thresholds", "manage_users", "change_technical_settings"}
    ),
    UserGroup.ADMIN: frozenset({"run", "read", "edit_thresholds", "manage_users"}),
    UserGroup.USER: frozenset({"run", "read"}),
}


def rights_of(group: UserGroup) -> frozenset[str]:
    return _GROUP_RIGHTS[group]


async def current_group() -> UserGroup:
    """Заглушка Ф1: пока нет аутентификации, все запросы идут как `user`.

    Именно `user`, а не `engineer`: заглушка обязана быть наименее правой из
    возможных. Иначе Ф5 включит аутентификацию и обнаружит, что часть роутеров
    работала только потому, что заглушка была всесильной.
    """
    return UserGroup.USER


GroupDep = Annotated[UserGroup, Depends(current_group)]


def require_right(right: str) -> Callable[[UserGroup], UserGroup]:
    """Фабрика зависимости: `Depends(require_right("edit_thresholds"))`.

    Ф1 отдаёт группу заглушкой — реальная аутентификация приходит в Ф5. Форма
    проверки при этом уже настоящая, чтобы Ф5 подставил источник, а не переписал
    все роутеры.
    """

    def _check(group: GroupDep) -> UserGroup:
        if right not in rights_of(group):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"группе {group.value} не выдано право {right}",
            )
        return group

    return _check
