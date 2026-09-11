"""Пароли и токены: bcrypt для хранения, JWT для сессии.

Два правила, которые легко нарушить без злого умысла:

- **Пустой секрет — это не слабая подпись, а её отсутствие.** Токен, подписанный
  пустой строкой, подделывается кем угодно, поэтому при пустом `JWT_SECRET` мы
  не выпускаем токены вовсе (тот же класс, что урок L1: пустой ответ и
  недоступный ответ — разные случаи).
- **Пароль не появляется нигде, кроме проверки.** Ни в логе, ни в ответе, ни в
  сообщении об ошибке: единственное, что о нём известно наружу, — подошёл он
  или нет.

Медленность bcrypt здесь не расход, а свойство: подбор пароля стоит столько же
времени, сколько проверка.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from ahrefs_cases import config
from ahrefs_cases.storage import UserGroup

logger = logging.getLogger(__name__)


class TokenError(Exception):
    """Токен не принят. Наружу уходит один ответ, в лог — разная причина."""


class SecretMissingError(RuntimeError):
    """Сервис не может подписывать токены: секрет пуст."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Что мы кладём в токен: кто и с какой группой."""

    user_id: int
    email: str
    group: UserGroup


def hash_password(raw: str) -> str:
    """Хеш пароля для хранения. Соль генерируется на каждый пароль."""
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    """Подходит ли пароль. Ошибка формата хеша — «не подходит», а не падение.

    В базе может лежать что угодно: пустая строка после ручной правки, обрезанный
    хеш после переноса. Всё это означает «войти нельзя», и различать их снаружи
    незачем — в логе причина остаётся.
    """
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except ValueError as exc:
        logger.warning("verify_password: испорченный хеш в базе (%s)", exc)
        return False


def issue_token(claims: TokenClaims) -> str:
    """Выпустить токен на время из настроек."""
    secret = _secret()
    expires_at = datetime.now(UTC) + timedelta(hours=config.auth.jwt_ttl_hours)
    payload = {
        "sub": str(claims.user_id),
        "email": claims.email,
        "group": claims.group.value,
        "exp": expires_at,
    }
    return jwt.encode(payload, secret, algorithm=config.auth.jwt_algorithm)


def read_token(token: str) -> TokenClaims:
    """Разобрать токен или отказать, назвав причину в логе.

    Наружу причина не уходит: «подпись не та» и «срок истёк» одинаково означают
    «войдите заново», а подробности помогают подбирать токены.
    """
    try:
        payload = jwt.decode(token, _secret(), algorithms=[config.auth.jwt_algorithm])
        return TokenClaims(
            user_id=int(payload["sub"]),
            email=str(payload["email"]),
            group=UserGroup(payload["group"]),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        logger.info("токен отклонён (%s): %s", type(exc).__name__, exc)
        message = "токен не принят"
        raise TokenError(message) from exc


def _secret() -> str:
    secret = config.auth.jwt_secret
    if not secret:
        message = (
            "JWT_SECRET пуст: токены не выпускаются и не принимаются. "
            "Подпись пустым секретом подделывается кем угодно"
        )
        raise SecretMissingError(message)
    return secret
