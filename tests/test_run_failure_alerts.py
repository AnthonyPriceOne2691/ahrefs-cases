"""Упавший прогон приходит в Telegram — один раз, с номером и причиной.

Прогон закрывается `failed` в пяти местах, и объявляет о нём не каждое, а
реапер — раз в тик, по отметке «объявлено до» (время закрытия и номер). Здесь —
правило отметки: первый запуск историю не объявляет, доставленное не
повторяется, отказ Telegram повторяется в следующий тик, два прогона с одним
временем закрытия не теряют друг друга. И отправка: токен бота — часть адреса,
поэтому в журнал не попадает даже при ошибке сети.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.storage import RunStatus, UserGroup
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.workers import telegram
from ahrefs_cases.workers.failed_runs import announce_failed_runs

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
_BOT = "123456:alerts-test-bot"  # pragma: allowlist secret


class _Mark:
    def __init__(self, value: tuple[datetime, int] | None) -> None:
        self.value = value

    def read(self) -> tuple[datetime, int] | None:
        return self.value

    def write(self, at: datetime, run_id: int) -> None:
        self.value = (at, run_id)


class _Chat:
    """Подменённый Telegram: принимает, пока `up`, и помнит принятое."""

    def __init__(self) -> None:
        self.up = True
        self.texts: list[str] = []

    async def send(self, text: str) -> bool:
        if self.up:
            self.texts.append(text)
        return self.up


async def _author(session: AsyncSession) -> int:
    user = User(
        email="alerts@test.local",
        full_name="Алерты",
        password_hash=security.hash_password("очень-длинный-пароль"),
        group=UserGroup.USER,
    )
    session.add(user)
    await session.flush()
    return user.id


async def _run(
    session: AsyncSession, author: int, status: RunStatus, closed: datetime, error: str = ""
) -> Run:
    run = Run(
        started_by=author,
        status=status,
        finished_at=closed,
        error=error,
        params_snapshot={"stage": "stage2"},
    )
    session.add(run)
    await session.flush()
    return run


async def test_first_tick_marks_now_and_announces_no_history(db_session: AsyncSession) -> None:
    """X1: отметки нет (первый запуск, очищенный Redis) — история новостью не считается."""
    author = await _author(db_session)
    await _run(db_session, author, RunStatus.FAILED, NOW - timedelta(days=2), "старое")
    mark, chat = _Mark(None), _Chat()

    assert await announce_failed_runs(db_session, mark, chat.send, NOW) == []
    assert chat.texts == [] and mark.value == (NOW, 0)


async def test_each_failure_is_announced_once_with_its_reason(db_session: AsyncSession) -> None:
    """X2: упавшие после отметки — по одному сообщению, по порядку; повтора нет.

    Удачные и идущие прогоны не объявляются; пустая причина названа словами.
    """
    author = await _author(db_session)
    first = await _run(
        db_session, author, RunStatus.FAILED, NOW + timedelta(minutes=1), "Ahrefs 500"
    )
    await _run(db_session, author, RunStatus.DONE, NOW + timedelta(minutes=2))
    second = await _run(db_session, author, RunStatus.FAILED, NOW + timedelta(minutes=3))
    mark, chat = _Mark((NOW, 0)), _Chat()

    assert await announce_failed_runs(db_session, mark, chat.send, NOW) == [first.id, second.id]
    assert chat.texts == [
        f"Ahrefs Cases: прогон №{first.id} (ступень stage2) упал — Ahrefs 500",
        f"Ahrefs Cases: прогон №{second.id} (ступень stage2) упал — причина не записана",
    ]
    assert await announce_failed_runs(db_session, mark, chat.send, NOW) == []
    assert len(chat.texts) == 2


async def test_a_refused_message_is_retried_next_tick(db_session: AsyncSession) -> None:
    """X3: Telegram не принял — отметка стоит, и следующий тик пробует тот же прогон."""
    author = await _author(db_session)
    run = await _run(db_session, author, RunStatus.FAILED, NOW + timedelta(minutes=1), "таймаут")
    mark, chat = _Mark((NOW, 0)), _Chat()

    chat.up = False
    assert await announce_failed_runs(db_session, mark, chat.send, NOW) == []
    assert mark.value == (NOW, 0)
    chat.up = True
    assert await announce_failed_runs(db_session, mark, chat.send, NOW) == [run.id]


async def test_two_failures_closed_at_one_moment_both_arrive(db_session: AsyncSession) -> None:
    """X4: отметка — пара «время, номер»: второй прогон с тем же временем не теряется.

    Отметка только по времени и строгое «больше» пропустили бы его, если бы
    первый ушёл, а второй упёрся в отказ Telegram.
    """
    author = await _author(db_session)
    at = NOW + timedelta(minutes=1)
    first = await _run(db_session, author, RunStatus.FAILED, at, "один")
    second = await _run(db_session, author, RunStatus.FAILED, at, "два")
    mark, chat = _Mark((NOW, 0)), _Chat()

    calls = 0

    async def only_first(text: str) -> bool:
        nonlocal calls
        calls += 1
        return await chat.send(text) if calls == 1 else False

    assert await announce_failed_runs(db_session, mark, only_first, NOW) == [first.id]
    assert await announce_failed_runs(db_session, mark, chat.send, NOW) == [second.id]


@pytest.fixture
def telegram_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.alerts, "telegram_bot_token", SecretStr(_BOT))
    monkeypatch.setattr(config.alerts, "telegram_chat_id", "-100500")


async def test_send_posts_chat_and_text(telegram_on: None) -> None:
    """X5: отправка — POST `sendMessage` с чатом и текстом; длинный текст режется, а не теряется."""
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    assert await telegram.send("я" * 5000, transport=httpx.MockTransport(answer))
    assert seen[0].url.path == f"/bot{_BOT}/sendMessage"
    form = dict(httpx.QueryParams(seen[0].content.decode()))
    assert form["chat_id"] == "-100500" and len(form["text"]) == 4000


async def test_a_network_error_keeps_the_token_out_of_the_log(
    telegram_on: None, caplog: pytest.LogCaptureFixture
) -> None:
    """X6: ошибка сети и отказ — False и строка в журнале, но токена в ней нет.

    Текст исключения httpx содержит адрес запроса, а в адресе — токен бота.
    """

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"не достучались до {request.url}", request=request)

    def refused(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False})

    with caplog.at_level(logging.WARNING):
        assert not await telegram.send("x", transport=httpx.MockTransport(broken))
        assert not await telegram.send("x", transport=httpx.MockTransport(refused))
    assert [r.getMessage() for r in caplog.records] == ["telegram_unreachable", "telegram_refused"]
    assert _BOT not in caplog.text and all(_BOT not in str(r.__dict__) for r in caplog.records)


async def test_an_unset_channel_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """X7: канал не настроен — False без запроса; настроен наполовину — назван недостающий."""
    monkeypatch.setattr(config.alerts, "telegram_bot_token", SecretStr(""))
    monkeypatch.setattr(config.alerts, "telegram_chat_id", "-100500")

    def must_not_call(_: httpx.Request) -> httpx.Response:
        raise AssertionError("запрос при выключенном канале")

    assert not await telegram.send("x", transport=httpx.MockTransport(must_not_call))
    assert config.alerts.missing_half == "TELEGRAM_BOT_TOKEN"
