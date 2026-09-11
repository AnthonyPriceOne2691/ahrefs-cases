"""Управление людьми: кто заведён, в какой группе и что ему можно.

Список сотрудников заказчик так и не прислал, и ждать его незачем:
администратор заводит людей сам. Пароль при этом **генерируется и показывается
один раз** — почтовый ящик переживает пароль, а придумывать его руководителю не
дело.

Права устроены так же, как в CRM агентства: группа даёт набор, **личное право
перекрывает группу** в обе стороны. «Этому человеку можно править пороги, хотя
он в группе пользователей» и «этому — нельзя, хотя он админ» выражаются одним
полем, а не новой ролью.

Три защиты перенесены оттуда же вместе с причинами: нельзя разжаловать
последнего администратора (система остаётся без управления), нельзя выключить
себя (дверь запирается изнутри), почта уникальна (она же логин).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from ahrefs_cases.api.deps import (
    ALL_RIGHTS,
    SessionDep,
    UserDep,
    require_right,
    rights_of,
    rights_of_user,
)
from ahrefs_cases.api.schemas import MAX_PAGE
from ahrefs_cases.api.security import generate_password, hash_password
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_right("manage_users"))],
)


class UserRow(BaseModel):
    """Человек в списке: группа, активность и то, что решено лично про него."""

    id: int
    email: str
    full_name: str
    group: str
    is_active: bool
    personal_rights: dict[str, bool]
    rights: list[str]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(default="", max_length=255)
    group: UserGroup = UserGroup.USER


class UserPatch(BaseModel):
    """Что можно поменять. Незаданное поле не трогается."""

    group: UserGroup | None = None
    is_active: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    personal_rights: dict[str, bool] | None = None
    """Личные права целиком: `{"edit_thresholds": true}` выдаёт, `false`
    отбирает, отсутствие ключа — «как в группе»."""


class RightsCatalog(BaseModel):
    """Какие права существуют и что даёт каждая группа.

    Экрану это нужно, чтобы отличить право «как в группе» от выданного лично:
    без справочника он держал бы вторую копию таблицы прав, а копия расходится
    молча — ровно тогда, когда таблицу правят (урок L97).
    """

    rights: list[str]
    groups: dict[str, list[str]]


class UserWithPassword(BaseModel):
    """Ответ на заведение и перевыпуск. Пароль показывается **один раз**."""

    user: UserRow
    password: str


@router.get("", response_model=list[UserRow])
async def list_users(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserRow]:
    """Кто заведён. Выданное точечно право видно строкой, а не выводится из роли."""
    stmt = select(User).order_by(User.email).limit(limit).offset(offset)
    return [_row(user) for user in (await session.execute(stmt)).scalars().all()]


@router.get("/rights", response_model=RightsCatalog)
async def rights_catalog() -> RightsCatalog:
    """Справочник прав — из той же таблицы, которую проверяют роутеры.

    Объявлен выше маршрутов с `{user_id}`: ниже слово `rights` уехало бы в
    целочисленный параметр (та же ловушка, что поймала смету прогона).
    """
    return RightsCatalog(
        rights=sorted(ALL_RIGHTS),
        groups={group.value: sorted(rights_of(group)) for group in UserGroup},
    )


@router.post("", response_model=UserWithPassword, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: SessionDep) -> UserWithPassword:
    """Завести человека и выдать ему пароль — один раз, в ответе."""
    await _refuse_taken_email(session, payload.email)

    password = generate_password()
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(password),
        group=payload.group,
        is_active=True,
        permissions={},
    )
    session.add(user)
    await session.flush()
    # Пароль в лог не попадает ни здесь, ни при перевыпуске: в логе только факт.
    logger.info("user_created", extra={"email": user.email, "group": user.group.value})
    return UserWithPassword(user=_row(user), password=password)


@router.patch("/{user_id}", response_model=UserRow)
async def patch_user(
    user_id: int, payload: UserPatch, session: SessionDep, actor: UserDep
) -> UserRow:
    """Сменить группу, включить-выключить, выдать или отобрать личное право."""
    user = await _get_or_404(session, user_id)
    patch = payload.model_dump(exclude_unset=True)

    if patch.get("is_active") is False and user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="нельзя выключить свою учётную запись: включить её будет некому",
        )
    if "group" in patch and patch["group"] is not UserGroup.ADMIN:
        await _refuse_last_admin(session, user)
    if "personal_rights" in patch and patch["personal_rights"] is not None:
        _refuse_unknown_rights(patch["personal_rights"])
        user.permissions = dict(patch["personal_rights"])

    if patch.get("group") is not None:
        user.group = patch["group"]
    if patch.get("is_active") is not None:
        user.is_active = bool(patch["is_active"])
    if patch.get("full_name") is not None:
        user.full_name = str(patch["full_name"])

    await session.flush()
    logger.info("user_updated", extra={"user_id": user.id, "fields": sorted(patch)})
    return _row(user)


@router.post("/{user_id}/password", response_model=UserWithPassword)
async def reset_password(user_id: int, session: SessionDep) -> UserWithPassword:
    """Перевыпустить пароль. Старый перестаёт работать сразу."""
    user = await _get_or_404(session, user_id)
    password = generate_password()
    user.password_hash = hash_password(password)
    await session.flush()
    logger.info("user_password_reset", extra={"user_id": user.id})
    return UserWithPassword(user=_row(user), password=password)


async def _get_or_404(session: SessionDep, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"пользователя {user_id} нет"
        )
    return user


async def _refuse_taken_email(session: SessionDep, email: str) -> None:
    """Почта — это логин, и второй такой быть не может."""
    taken = (await session.execute(select(User).where(User.email == email))).scalars().first()
    if taken is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"почта {email} уже занята"
        )


async def _refuse_last_admin(session: SessionDep, user: User) -> None:
    """Последнего администратора не разжаловать: управлять станет некому.

    Защита перенесена из CRM агентства вместе с причиной — там она появилась
    после того, как система однажды осталась без администратора.
    """
    if user.group is not UserGroup.ADMIN:
        return
    admins = int(
        await session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.group == UserGroup.ADMIN, User.is_active.is_(True))
        )
        or 0
    )
    if admins <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="это последний администратор: снять группу с него нельзя",
        )


def _refuse_unknown_rights(rights: dict[str, bool]) -> None:
    """Выдать можно только то право, которое кто-то проверяет.

    Неизвестное имя в JSONB выглядело бы как выданный доступ, а означало бы
    ровно ничего — обещание вместо права (урок L23).
    """
    unknown = sorted(set(rights) - ALL_RIGHTS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"неизвестные права: {', '.join(unknown)}. Известные: {', '.join(sorted(ALL_RIGHTS))}",
        )


def _row(user: User) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        group=user.group.value,
        is_active=user.is_active,
        personal_rights=dict(user.permissions or {}),
        rights=sorted(rights_of_user(user)),
    )
