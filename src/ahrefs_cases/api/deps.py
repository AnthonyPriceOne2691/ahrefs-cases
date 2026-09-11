"""Зависимости FastAPI: сессия и права.

Право — строка, роль — набор прав. Проверка стоит зависимостью на роутере, а не
условием внутри обработчика: иначе «кто может править пороги» расползается по
коду копиями, и граница сдвигается без ревью.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.api.security import SecretMissingError, TokenError, read_token
from ahrefs_cases.storage import UserGroup, session_scope
from ahrefs_cases.storage.models.user import User

logger = logging.getLogger(__name__)


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


ALL_RIGHTS: frozenset[str] = frozenset().union(*_GROUP_RIGHTS.values())
"""Все известные права. Выдать можно только такое: право, которого не
проверяет ни один роутер, — обещание, а не доступ."""


def rights_of(group: UserGroup) -> frozenset[str]:
    return _GROUP_RIGHTS[group]


def rights_of_user(user: User) -> frozenset[str]:
    """Права человека: группа даёт набор, **личное решение перекрывает его**.

    Приём из CRM агентства (`features/auth/rbac.py`): `{"edit_thresholds": true}`
    выдаёт право сверх группы, `false` — отбирает, даже если группа его даёт.
    Перекрытие работает в обе стороны нарочно: «этому человеку — нет» встречается
    так же часто, как «этому — да», и через роль оно не выражается вовсе.

    Права расходятся быстрее, чем роли: без этого первое же новое право
    потребовало бы четвёртой группы или правки кода.
    """
    granted = set(rights_of(user.group))
    for right, allowed in (user.permissions or {}).items():
        if allowed:
            granted.add(right)
        else:
            granted.discard(right)
    return frozenset(granted)


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="нужен действующий токен",
    headers={"WWW-Authenticate": "Bearer"},
)
"""Один ответ на все причины отказа: нет заголовка, чужая подпись, истёк срок,
пользователь выключен. Различать их снаружи — помогать подбирать токены;
в логе причина остаётся (урок L23 наоборот: здесь склейка сознательная)."""


async def current_user(request: Request, session: SessionDep) -> User:
    """Пользователь из заголовка `Authorization: Bearer <токен>`.

    Заглушка Ф1 возвращала группу `user` всем; теперь источник настоящий, а
    форма проверки прав не изменилась — `require_right` писался в Ф1 именно так.

    Пользователь перечитывается из базы, потому что токен живёт до 12 часов:
    выключенный за это время сотрудник обязан перестать входить сразу, а не
    когда истечёт его токен.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        logger.info("запрос без токена: %s %s", request.method, request.url.path)
        raise _UNAUTHORIZED
    try:
        claims = read_token(token)
    except TokenError as exc:
        raise _UNAUTHORIZED from exc
    except SecretMissingError as exc:
        # Не 401: это мисконфигурация сервиса, а не беда пользователя.
        logger.exception("токен не разобран: сервис без секрета подписи")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="сервис не настроен: нет секрета подписи токенов",
        ) from exc

    user = (await session.execute(select(User).where(User.id == claims.user_id))).scalars().first()
    if user is None or not user.is_active:
        logger.info("токен принят, но пользователь %s недоступен", claims.user_id)
        raise _UNAUTHORIZED
    return user


UserDep = Annotated[User, Depends(current_user)]


async def current_group(user: UserDep) -> UserGroup:
    """Группа запроса. Берётся из пользователя, а не из токена: см. `current_user`."""
    return user.group


GroupDep = Annotated[UserGroup, Depends(current_group)]


def require_right(right: str) -> Callable[[User], UserGroup]:
    """Фабрика зависимости: `Depends(require_right("edit_thresholds"))`.

    Источник прав менялся дважды, а роутеры — ни разу: сначала заглушка Ф1
    отдавала группу всем, потом появился токен, теперь права берутся у
    **пользователя** (личные поверх групповых). Ради этого форма и писалась.
    """

    def _check(user: UserDep) -> UserGroup:
        if right not in rights_of_user(user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"нет права {right}: группа {user.group.value}",
            )
        return user.group

    return _check
