"""Внешняя копия бэкапа и алерт о его сбое — исполнением скриптов, а не чтением.

Хранилище и Telegram подменяет один локальный HTTP-сервер: принимает PUT
объекта, отдаёт список и объект, принимает `sendMessage` и запоминает всё, что
пришло. Подпись SigV4 он не проверяет — это сделал прогон на S3-совместимом
сервере (verify-report поставки `offsite-backup-copy`); здесь — что уходит
(шифрованное, с SHA-256 тела в подписанном заголовке), когда кричать и чего не
видно в `ps`. Копию шифрует gpg: нет его — пропуск с причиной, но не в CI
(`CI=true`), где пропуск был бы ложным зелёным.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_STAMP = "2026-09-28-0330"
_OBJECT = f"/backups/ahrefs-cases/{_STAMP}.tar.gpg"
# Не настоящие учётки — значения для подменённых хранилища и Telegram.
_KEY_ID = "AKTESTOFFSITE"
_SIGNING = "offsite-signing-9f1c"  # pragma: allowlist secret
_PHRASE = "correct horse battery staple"  # pragma: allowlist secret
_BOT = "123456:offsite-test-bot"  # pragma: allowlist secret
_CHAT = "-100500"

pytestmark = pytest.mark.skipif(
    shutil.which("gpg") is None and not os.getenv("CI"),
    reason="нет gpg: внешняя копия шифруется им (в CI он есть, и там пропуск — красный)",
)


@dataclass
class _Seen:
    """Что пришло на подменённые хранилище и Telegram."""

    url: str = ""
    puts: list[tuple[str, dict[str, str], bytes]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    objects: dict[str, bytes] = field(default_factory=dict)
    refuse_puts: bool = False


def _handler(seen: _Seen) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            return  # вывод pytest — не журнал сервера

        def _body(self) -> bytes:
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def _answer(self, code: int, body: bytes = b"") -> None:
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_PUT(self) -> None:
            body = self._body()
            seen.puts.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
            if seen.refuse_puts:  # чужой ключ — 403, как ответит настоящее хранилище
                self._answer(403, b"<Error><Code>AccessDenied</Code></Error>")
                return
            seen.objects[urlsplit(self.path).path] = body
            self._answer(200)

        def do_POST(self) -> None:
            form = parse_qs(self._body().decode())
            if self.path != f"/bot{_BOT}/sendMessage" or form.get("chat_id") != [_CHAT]:
                self._answer(404)
                return
            seen.messages.append(form["text"][0])
            self._answer(200, b'{"ok":true}')

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if "list-type=2" in url.query:
                keys = "".join(f"<Key>{p.split('/', 2)[2]}</Key>" for p in sorted(seen.objects))
                self._answer(200, f"<ListBucketResult>{keys}</ListBucketResult>".encode())
                return
            body = seen.objects.get(url.path)
            if body is None:
                self._answer(404)
            else:
                self._answer(200, body)

    return Handler


@pytest.fixture
def seen() -> Iterator[_Seen]:
    record = _Seen()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(record))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    record.url = f"http://127.0.0.1:{server.server_port}"
    yield record
    server.shutdown()


@pytest.fixture
def gpg_home() -> Iterator[Path]:
    """Свой каталог gpg с коротким путём: сокет агента в длинный не влезает."""
    home = Path(tempfile.mkdtemp(prefix="gpg", dir="/tmp"))
    home.chmod(0o700)
    yield home
    env = {**os.environ, "GNUPGHOME": str(home)}
    subprocess.run(["gpgconf", "--kill", "gpg-agent"], env=env, capture_output=True, check=False)
    shutil.rmtree(home, ignore_errors=True)


def _env(seen: _Seen, gpg_home: Path, **extra: str) -> dict[str, str]:
    """Окружение скриптов: всё задано явно, `.env` разработчика не читается."""
    return {
        **os.environ,
        "ENV_FILE": "/nonexistent/.env",
        "GNUPGHOME": str(gpg_home),
        "OFFSITE_S3_ENDPOINT": seen.url,
        "OFFSITE_S3_REGION": "us-east-1",
        "OFFSITE_S3_BUCKET": "backups",
        "OFFSITE_S3_ACCESS_KEY_ID": _KEY_ID,
        "OFFSITE_S3_SECRET_ACCESS_KEY": _SIGNING,
        "OFFSITE_PASSPHRASE": _PHRASE,
        "TELEGRAM_BOT_TOKEN": _BOT,
        "TELEGRAM_CHAT_ID": _CHAT,
        "TELEGRAM_API_URL": seen.url,
        **extra,
    }


def _backup(tmp_path: Path) -> Path:
    target = tmp_path / "backups" / _STAMP
    target.mkdir(parents=True)
    (target / "cases.dump").write_bytes(b"PGDMP" + os.urandom(2048))
    (target / "casedata.tar").write_bytes(os.urandom(1024))
    (target / "README.txt").write_text("Бэкап Ahrefs Cases\n", encoding="utf-8")
    return target


def _run(script: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command = [str(_SCRIPTS / script), *args]
    return subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=120, check=False
    )


def _open(body: bytes, tmp_path: Path, gpg_home: Path) -> tarfile.TarFile:
    """Расшифровать то, что пришло в хранилище, тем же паролем."""
    sealed = tmp_path / "sealed.gpg"
    sealed.write_bytes(body)
    command = ["gpg", "--batch", "--quiet", "--pinentry-mode", "loopback", "--passphrase-fd", "0"]
    env = {**os.environ, "GNUPGHOME": str(gpg_home)}
    plain = subprocess.run(
        [*command, "--decrypt", str(sealed)],
        input=_PHRASE.encode(),
        capture_output=True,
        env=env,
        check=False,
    )
    assert plain.returncode == 0, plain.stderr.decode()
    return tarfile.open(fileobj=io.BytesIO(plain.stdout))


def test_the_copy_leaves_encrypted_and_its_digest_is_signed(
    tmp_path: Path, seen: _Seen, gpg_home: Path
) -> None:
    """Q1: наружу — шифрованный tar каталога; SHA-256 тела — в подписанном заголовке.

    Хранилище само отказывает, если тело не совпало с заголовком, поэтому
    заголовок обязан быть суммой именно отправленного. Открытого дампа в теле
    нет, расшифровка тем же паролем даёт тот же каталог.
    """
    backup = _backup(tmp_path)
    done = _run("offsite_push.sh", str(backup), env=_env(seen, gpg_home))

    assert done.returncode == 0, done.stderr
    assert [path for path, _, _ in seen.puts] == [_OBJECT]
    _, headers, body = seen.puts[0]
    assert headers["x-amz-content-sha256"] == hashlib.sha256(body).hexdigest()
    assert headers["authorization"].startswith(f"AWS4-HMAC-SHA256 Credential={_KEY_ID}/")
    assert "/us-east-1/s3/aws4_request" in headers["authorization"]
    assert b"PGDMP" not in body and b"cases.dump" not in body, "в хранилище ушла открытая копия"
    with _open(body, tmp_path, gpg_home) as archive:
        dump = archive.extractfile(f"{_STAMP}/cases.dump")
        assert dump is not None and dump.read() == (backup / "cases.dump").read_bytes()
    assert (backup.parent / ".offsite-last").read_text().split()[1] == _OBJECT.split("/", 2)[2]


def test_secrets_stay_off_the_command_line(tmp_path: Path, seen: _Seen, gpg_home: Path) -> None:
    """Q2: ключ бакета, пароль копии и токен бота не бывают в аргументах curl и gpg.

    Машина прода общая, и `ps` показывает аргументы всех процессов. Обёртки
    записывают свои аргументы и зовут настоящие программы.
    """
    shims, argv_log = tmp_path / "shims", tmp_path / "argv.log"
    shims.mkdir()
    for tool in ("curl", "gpg"):
        shim = shims / tool
        shim.write_text(f'#!/bin/sh\necho "$*" >> "{argv_log}"\nexec "{shutil.which(tool)}" "$@"\n')
        shim.chmod(0o755)
    env = _env(seen, gpg_home, PATH=f"{shims}{os.pathsep}{os.environ['PATH']}")

    assert _run("offsite_push.sh", str(_backup(tmp_path)), env=env).returncode == 0
    assert _run("notify.sh", "проверка", env=env).returncode == 0
    assert (
        _run("offsite_fetch.sh", "get", "latest", str(tmp_path / "back"), env=env).returncode == 0
    )

    argv = argv_log.read_text()
    assert argv.count("--aws-sigv4") == 3 and "sendMessage" not in argv
    for secret in (_SIGNING, _PHRASE, _BOT):
        assert secret not in argv, f"в аргументах видно: {secret[:6]}…"


def test_an_unset_copy_says_so_and_a_half_set_one_refuses(
    tmp_path: Path, seen: _Seen, gpg_home: Path
) -> None:
    """Q3: не настроена — строка и ноль; наполовину — отказ с именами недостающих.

    Полунастроенная копия хуже ненастроенной: она выглядит работающей.
    """
    backup = str(_backup(tmp_path))
    unset = {name: "" for name in _env(seen, gpg_home) if name.startswith("OFFSITE_")}
    quiet = _run("offsite_push.sh", backup, env=_env(seen, gpg_home, **unset))
    assert quiet.returncode == 0 and "не настроена" in quiet.stdout

    half = _env(seen, gpg_home, OFFSITE_PASSPHRASE="", OFFSITE_S3_REGION="")
    refused = _run("offsite_push.sh", backup, env=half)
    assert refused.returncode == 2
    assert "OFFSITE_S3_REGION" in refused.stderr and "OFFSITE_PASSPHRASE" in refused.stderr
    assert not seen.puts


def _stub_compose(tmp_path: Path, *, postgres_up: bool) -> str:
    """`docker compose` для backup.sh: postgres отвечает дампом, api — артефактами."""
    data = tmp_path / "casedata"
    data.mkdir()
    (data / "case.pdf").write_bytes(b"%PDF-stub")
    stub = tmp_path / "compose"
    listed = "echo postgres" if postgres_up else "true"
    stub.write_text(
        f'#!/bin/sh\ncase "$1" in\n  ps) {listed} ;;\n'
        f'  exec) [ "$3" = postgres ] && printf PGDMP-stub || tar -cf - -C "{data}" . ;;\nesac\n'
    )
    stub.chmod(0o755)
    return str(stub)


@pytest.mark.parametrize(
    ("refuse", "postgres_up", "sent", "alert"),
    [
        pytest.param(False, True, 1, "", id="Q4-local-then-offsite-no-alert"),
        pytest.param(True, True, 1, "снята, внешняя НЕ отправлена", id="Q5-copy-refused"),
        pytest.param(False, False, 0, "проверка стека", id="Q6-nothing-to-dump"),
    ],
)
def test_backup_cries_when_the_copy_does_not_leave(
    tmp_path: Path,
    seen: _Seen,
    gpg_home: Path,
    refuse: bool,
    postgres_up: bool,
    sent: int,
    alert: str,
) -> None:
    """Q4–Q6: удачный бэкап молчит; сбой — выход не нулём и ровно один алерт с шагом.

    «Не снята локальная» и «снята, но не ушла наружу» — разные беды: по первой
    восстанавливаться не из чего вовсе. Сбой внешней копии локальную не трогает.
    """
    seen.refuse_puts = refuse
    compose = _stub_compose(tmp_path, postgres_up=postgres_up)
    env = _env(seen, gpg_home, COMPOSE=compose, BACKUP_DIR=str(tmp_path / "backups"))
    done = _run("backup.sh", env=env)

    local = [p for p in (tmp_path / "backups").glob("*") if (p / "cases.dump").is_file()]
    assert len(seen.puts) == sent and len(local) == int(postgres_up)
    if not alert:
        assert done.returncode == 0 and seen.messages == [], done.stderr
        assert seen.puts[0][0] == f"/backups/ahrefs-cases/{local[0].name}.tar.gpg"
    else:
        assert done.returncode != 0 and len(seen.messages) == 1
        assert alert in seen.messages[0]


def test_notify_without_telegram_prints_instead_of_failing(seen: _Seen, gpg_home: Path) -> None:
    """Q7: канал не настроен — текст в stderr с пометкой и ноль: бэкап не падает из-за чата."""
    done = _run("notify.sh", "бэкап упал", env=_env(seen, gpg_home, TELEGRAM_BOT_TOKEN=""))

    assert done.returncode == 0 and seen.messages == []
    assert "НЕ отправлен" in done.stderr and "бэкап упал" in done.stderr


def test_fetch_returns_what_push_sent(tmp_path: Path, seen: _Seen, gpg_home: Path) -> None:
    """Q8: обратно приходит тот же каталог; неверный пароль — отказ словами, без каталога.

    Расшифровка идёт целиком до распаковки: испорченная копия не успевает
    наполовину распаковаться и выглядеть бэкапом.
    """
    backup, back = _backup(tmp_path), tmp_path / "back"
    env = _env(seen, gpg_home)
    assert _run("offsite_push.sh", str(backup), env=env).returncode == 0
    assert _run("offsite_fetch.sh", "list", env=env).stdout.split() == [f"{_STAMP}.tar.gpg"]

    fetched = _run("offsite_fetch.sh", "get", "latest", str(back), env=env)
    assert fetched.returncode == 0, fetched.stderr
    for name in ("cases.dump", "casedata.tar", "README.txt"):
        assert (back / _STAMP / name).read_bytes() == (backup / name).read_bytes()
    assert f"scripts/restore.sh {back / _STAMP} --yes" in fetched.stdout

    wrong_env = _env(seen, gpg_home, OFFSITE_PASSPHRASE="not-the-phrase")
    wrong = _run("offsite_fetch.sh", "get", "latest", str(tmp_path / "wrong"), env=wrong_env)
    assert wrong.returncode != 0 and "не расшифровано" in wrong.stderr
    assert not (tmp_path / "wrong" / _STAMP).exists()
