"""Сторож здоровья хоста кричит, когда состояние сменилось, — и только тогда.

`scripts/healthcheck.sh` идёт из крона раз в пять минут и смотрит то, чего
изнутри контейнеров не видно: запущены ли и здоровы контейнеры (Docker по
unhealthy их не перезапускает нарочно), отвечает ли API через web, свежий ли
ночной бэкап — крон, не запустившийся вовсе, `backup.sh` не поймает.
Компоуз подменяет заглушка, API и Telegram — локальный HTTP-сервер.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "healthcheck.sh"
_BOT = "123456:health-test-bot"  # pragma: allowlist secret
_HEALTHY = "\n".join(
    f"{s} running {h}"
    for s, h in [
        ("postgres", "healthy"),
        ("redis", "healthy"),
        ("api", "healthy"),
        ("worker", "healthy"),
        ("reaper", "healthy"),
        ("web", "healthy"),
    ]
)


@dataclass
class _Host:
    url: str = ""
    api_ok: bool = True
    messages: list[str] = field(default_factory=list)


@pytest.fixture
def host() -> Iterator[_Host]:
    record = _Host()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return

        def _answer(self, code: int, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            ok = self.path == "/api/health" and record.api_ok
            self._answer(200 if ok else 503, b'{"status": "ok"}' if ok else b"{}")

        def do_POST(self) -> None:
            size = int(self.headers.get("Content-Length") or 0)
            record.messages.append(parse_qs(self.rfile.read(size).decode())["text"][0])
            self._answer(200, b'{"ok":true}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    record.url = f"http://127.0.0.1:{server.server_port}"
    yield record
    server.shutdown()
    server.server_close()  # иначе сокет закроет сборщик мусора — ResourceWarning


def _check(
    tmp_path: Path, host: _Host, services: str = _HEALTHY
) -> subprocess.CompletedProcess[str]:
    compose = tmp_path / "compose"
    (tmp_path / "ps.txt").write_text(services + "\n")
    compose.write_text(f'#!/bin/sh\ncat "{tmp_path / "ps.txt"}"\n')
    compose.chmod(0o755)
    env = {
        **os.environ,
        "ENV_FILE": "/nonexistent/.env",
        "COMPOSE": str(compose),
        "BACKUP_DIR": str(tmp_path / "backups"),
        "STATE_FILE": str(tmp_path / "state" / "health.state"),
        "HEALTH_URL": f"{host.url}/api/health",
        "TELEGRAM_BOT_TOKEN": _BOT,
        "TELEGRAM_CHAT_ID": "-100500",
        "TELEGRAM_API_URL": host.url,
    }
    return subprocess.run(
        [str(_SCRIPT)], env=env, capture_output=True, text=True, timeout=60, check=False
    )


def _fresh_backup(tmp_path: Path, age_hours: float = 1) -> Path:
    backup = tmp_path / "backups" / "2026-09-28-0330"
    backup.mkdir(parents=True, exist_ok=True)
    moment = time.time() - age_hours * 3600
    os.utime(backup, (moment, moment))
    return backup


def test_a_trouble_is_told_once_and_its_end_too(tmp_path: Path, host: _Host) -> None:
    """X8: всё в порядке — тишина; беда — один алерт; та же беда — тишина; прошла — алерт.

    Алерт, повторяющийся каждые пять минут, перестают читать к обеду.
    """
    _fresh_backup(tmp_path)
    assert _check(tmp_path, host).returncode == 0
    assert host.messages == []

    sick = _HEALTHY.replace("worker running healthy", "worker running unhealthy")
    sick = sick.replace("reaper running healthy", "reaper exited ")
    host.api_ok = False
    assert _check(tmp_path, host, sick).returncode == 0
    assert _check(tmp_path, host, sick).returncode == 0
    assert len(host.messages) == 1
    for trouble in ("worker: unhealthy", "reaper: exited", "API не отвечает ok"):
        assert trouble in host.messages[0]

    host.api_ok = True
    assert _check(tmp_path, host).returncode == 0
    assert len(host.messages) == 2 and host.messages[1].startswith("Ahrefs Cases: снова в порядке")


def test_a_backup_that_did_not_run_is_a_trouble(tmp_path: Path, host: _Host) -> None:
    """X9: ночной бэкап старше суток с запасом (26 ч) или его нет вовсе — беда.

    Крон, который не запустился, `backup.sh` не поймает: он просто не исполнится.
    """
    _fresh_backup(tmp_path, age_hours=30)
    _check(tmp_path, host)

    assert len(host.messages) == 1 and "последний бэкап старше 26 ч" in host.messages[0]
