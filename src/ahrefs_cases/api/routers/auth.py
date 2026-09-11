"""Вход в сервис и ответ на вопрос «кто я и что мне можно».

Ответ на неудачный вход **один на все причины**: неизвестная почта, неверный
пароль, выключенный сотрудник. Разные ответы превратили бы форму входа в
перечислитель учётных записей — по ним собирается список адресов агентства.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ahrefs_cases import config
from ahrefs_cases.api.deps import SessionDep, UserDep, rights_of
from ahrefs_cases.api.security import (
    SecretMissingError,
    TokenClaims,
    issue_token,
    verify_password,
)
from ahrefs_cases.storage.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_DENIED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="неверная почта или пароль",
)


class LoginRequest(BaseModel):
    """Почта здесь — ключ поиска, а не адрес для писем.

    Поэтому `str`, а не `EmailStr`: строгая проверка формата потребовала бы
    зависимости `email-validator` ради поля, по которому мы делаем `SELECT`.
    Адрес заводится командой `useradd`, там он и проверяется человеком.
    """

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    """Токен и то, что интерфейсу нужно сразу: группа и список прав."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 — схема OAuth2, а не пароль
    expires_in_hours: int
    group: str
    rights: list[str]


class WhoAmI(BaseModel):
    email: str
    full_name: str
    group: str
    rights: list[str]


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    """Выдать токен по почте и паролю."""
    user = (
        (await session.execute(select(User).where(User.email == payload.email))).scalars().first()
    )
    # Пароль проверяется даже у ненайденного пользователя — по фиктивному хешу:
    # иначе ответ на неизвестную почту приходит заметно быстрее, и разница во
    # времени рассказывает то же, что рассказал бы разный текст ошибки.
    hashed = user.password_hash if user is not None else _DUMMY_HASH
    matched = verify_password(payload.password, hashed)
    if user is None or not matched or not user.is_active:
        logger.info("неудачный вход: %s", payload.email)
        raise _DENIED

    try:
        token = issue_token(TokenClaims(user_id=user.id, email=user.email, group=user.group))
    except SecretMissingError as exc:
        logger.exception("вход невозможен: сервис без секрета подписи")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="сервис не настроен: нет секрета подписи токенов",
        ) from exc

    logger.info("вход: %s, группа %s", user.email, user.group.value)
    return TokenResponse(
        access_token=token,
        expires_in_hours=config.auth.jwt_ttl_hours,
        group=user.group.value,
        rights=sorted(rights_of(user.group)),
    )


@router.get("/me", response_model=WhoAmI)
async def me(user: UserDep) -> WhoAmI:
    """Кто я и что мне можно. Интерфейс рисует навигацию по этому списку."""
    return WhoAmI(
        email=user.email,
        full_name=user.full_name,
        group=user.group.value,
        rights=sorted(rights_of(user.group)),
    )


_DUMMY_HASH = "$2b$12$" + "." * 53
"""Заведомо неподходящий хеш правильной формы — чтобы время ответа на
неизвестную почту совпадало с временем ответа на неверный пароль."""
