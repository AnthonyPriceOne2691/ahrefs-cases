"""Внешняя копия бэкапа и алерт о его сбое — исполнением скриптов, а не чтением.

Копии `scripts/backup.sh` лежали на том же диске, что и сервис: от потери
машины они не спасали, а упавший ночью бэкап молчал до дня восстановления.
Теперь копия шифруется и уходит в S3-совместимое хранилище
(`scripts/offsite_push.sh`), обратно — `scripts/offsite_fetch.sh`, а любой
сбой бэкапа — алерт в Telegram (`scripts/notify.sh`).

Хранилище и Telegram подменяет один локальный HTTP-сервер: принимает PUT
объекта, отдаёт список и объект, принимает `sendMessage` и запоминает всё, что
пришло. Подпись SigV4 он не проверяет — это сделал прогон на S3-совместимом
сервере (verify-report поставки `offsite-backup-copy`); здесь проверяется то,
что можно проверить без сети: что уходит (шифрованное, с SHA-256 тела в
подписанном заголовке), когда кричать и чего не видно в `ps`.

Шифрует копию gpg. На Mac разработчика его может не быть — тогда проверки
пропускаются с причиной; в CI (`CI=true`) пропуск был бы ложным зелёным,
поэтому там они идут и падают, если gpg нет.
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

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
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
            size = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(size) if size else b""

        def _answer(self, code: int, body: bytes = b"") -> None:
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_PUT(self) -> None:
            body = self._body()
            seen.puts.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
            if seen.refuse_puts:
                self._answer(403, b"<Error><Code>AccessDenied</Code></Error>")
                return
            seen.objects[urlsplit(self.path).path] = body
            self._answer(200)

        def do_POST(self) -> None:
            form = parse_qs(self._body().decode("utf-8"))
            if self.path != f"/bot{_BOT}/sendMessage" or form.get("chat_id") != [_CHAT]:
                self._answer(404)
                return
            seen.messages.append(form["text"][0])
            self._answer(200, b'{"ok":true}')

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if "list-type=2" in url.query:
                keys = "".join(
                    f"<Contents><Key>{path.split('/', 2)[2]}</Key></Contents>"
                    for path in sorted(seen.objects)
                )
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
    try:
        yield record
    finally:
        server.shutdown()


@pytest.fixture
def gnupg_home() -> Iterator[Path]:
    """Свой каталог gpg с коротким путём: сокет агента в длинный не влезает."""
    home = Path(tempfile.mkdtemp(prefix="gpg", dir="/tmp"))
    home.chmod(0o700)
    try:
        yield home
    finally:
        subprocess.run(
            ["gpgconf", "--kill", "gpg-agent"],
            env={**os.environ, "GNUPGHOME": str(home)},
            capture_output=True,
            check=False,
        )
        shutil.rmtree(home, ignore_errors=True)


def _env(seen: _Seen, gnupg_home: Path, **extra: str) -> dict[str, str]:
    """Окружение скриптов: всё задано явно, `.env` разработчика не читается."""
    return {
        **os.environ,
        "ENV_FILE": "/nonexistent/.env",
        "GNUPGHOME": str(gnupg_home),
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
    return subprocess.run(
        [str(_SCRIPTS / script), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _open(body: bytes, tmp_path: Path, gnupg_home: Path) -> tarfile.TarFile:
    """Расшифровать то, что пришло в хранилище, тем же паролем."""
    sealed = tmp_path / "sealed.gpg"
    sealed.write_bytes(body)
    plain = subprocess.run(
        [
            "gpg",
            "--batch",
            "--quiet",
            "--pinentry-mode",
            "loopback",
            "--no-symkey-cache",
            "--passphrase-fd",
            "0",
            "--decrypt",
            str(sealed),
        ],
        input=_PHRASE.encode(),
        capture_output=True,
        check=True,
        env={**os.environ, "GNUPGHOME": str(gnupg_home)},
    )
    return tarfile.open(fileobj=io.BytesIO(plain.stdout))


def test_the_copy_leaves_encrypted_and_its_digest_is_signed(
    tmp_path: Path, seen: _Seen, gnupg_home: Path
) -> None:
    """Q1: наружу уходит шифрованный tar каталога, SHA-256 тела — в подписанном заголовке.

    Хранилище само отказывает, если принятое тело не совпало с заголовком, —
    поэтому заголовок обязан быть суммой именно отправленного. Открытого
    дампа в теле нет, а расшифровка тем же паролем даёт тот же каталог.
    """
    backup = _backup(tmp_path)
    done = _run("offsite_push.sh", str(backup), env=_env(seen, gnupg_home))

    assert done.returncode == 0, done.stderr
    assert [path for path, _, _ in seen.puts] == [_OBJECT]
    _, headers, body = seen.puts[0]
    assert headers["x-amz-content-sha256"] == hashlib.sha256(body).hexdigest()
    assert headers["authorization"].startswith(f"AWS4-HMAC-SHA256 Credential={_KEY_ID}/")
    assert "/us-east-1/s3/aws4_request" in headers["authorization"]
    assert b"PGDMP" not in body and b"cases.dump" not in body, "в хранилище ушла открытая копия"

    with _open(body, tmp_path, gnupg_home) as archive:
        dump = archive.extractfile(f"{_STAMP}/cases.dump")
        assert dump is not None
        assert dump.read() == (backup / "cases.dump").read_bytes()
    assert (backup.parent / ".offsite-last").read_text().split()[1] == _OBJECT.split("/", 2)[2]


def test_secrets_stay_off_the_command_line(tmp_path: Path, seen: _Seen, gnupg_home: Path) -> None:
    """Q2: ни ключ бакета, ни пароль копии, ни токен бота не бывают в аргументах.

    Машина прода общая, и `ps` показывает аргументы всех процессов. Обёртки
    curl и gpg записывают свои аргументы и зовут настоящие программы.
    """
    shims = tmp_path / "shims"
    shims.mkdir()
    argv_log = tmp_path / "argv.log"
    for tool in ("curl", "gpg"):
        real = shutil.which(tool)
        assert real is not None
        shim = shims / tool
        shim.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{argv_log}"\nexec "{real}" "$@"\n')
        shim.chmod(0o755)
    env = _env(seen, gnupg_home, PATH=f"{shims}{os.pathsep}{os.environ['PATH']}")

    backup = _backup(tmp_path)
    assert _run("offsite_push.sh", str(backup), env=env).returncode == 0
    assert _run("notify.sh", "проверка", env=env).returncode == 0
    fetched = _run("offsite_fetch.sh", "get", "latest", str(tmp_path / "back"), env=env)
    assert fetched.returncode == 0, fetched.stderr

    argv = argv_log.read_text()
    assert argv.count("--aws-sigv4") == 3 and "sendMessage" not in argv
    for secret in (_SIGNING, _PHRASE, _BOT):
        assert secret not in argv, f"в аргументах видно: {secret[:6]}…"


def test_an_unset_copy_says_so_and_a_half_set_one_refuses(
    tmp_path: Path, seen: _Seen, gnupg_home: Path
) -> None:
    """Q3: не настроена — строка и ноль; настроена наполовину — отказ с именами.

    Полунастроенная копия хуже ненастроенной: она выглядит работающей.
    """
    backup = _backup(tmp_path)
    unset = {name: "" for name in _env(seen, gnupg_home) if name.startswith("OFFSITE_")}

    quiet = _run("offsite_push.sh", str(backup), env=_env(seen, gnupg_home, **unset))
    assert quiet.returncode == 0 and "не настроена" in quiet.stdout

    half = _run(
        "offsite_push.sh",
        str(backup),
        env=_env(seen, gnupg_home, OFFSITE_PASSPHRASE="", OFFSITE_S3_REGION=""),
    )
    assert half.returncode == 2
    assert "OFFSITE_S3_REGION" in half.stderr and "OFFSITE_PASSPHRASE" in half.stderr
    assert not seen.puts


def _stub_compose(tmp_path: Path, *, postgres_up: bool) -> str:
    """`docker compose` для backup.sh: postgres отвечает дампом, api — артефактами."""
    data = tmp_path / "casedata"
    data.mkdir()
    (data / "case.pdf").write_bytes(b"%PDF-stub")
    stub = tmp_path / "compose"
    services = "echo postgres" if postgres_up else "true"
    stub.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f"  ps) {services} ;;\n"
        '  exec) [ "$3" = postgres ] && printf "PGDMP-stub" || tar -cf - -C "'
        f'{data}" . ;;\n'
        "esac\n"
    )
    stub.chmod(0o755)
    return str(stub)


def _backup_sh(
    tmp_path: Path, seen: _Seen, gnupg_home: Path, *, postgres_up: bool = True
) -> subprocess.CompletedProcess[str]:
    env = _env(
        seen,
        gnupg_home,
        COMPOSE=_stub_compose(tmp_path, postgres_up=postgres_up),
        BACKUP_DIR=str(tmp_path / "backups"),
    )
    return _run("backup.sh", env=env)


def test_backup_sends_the_copy_after_the_local_one(
    tmp_path: Path, seen: _Seen, gnupg_home: Path
) -> None:
    """Q4: удачный бэкап — локальная копия, внешняя, и ни одного алерта."""
    done = _backup_sh(tmp_path, seen, gnupg_home)

    assert done.returncode == 0, done.stderr
    local = [path for path in (tmp_path / "backups").iterdir() if path.is_dir()]
    assert len(local) == 1 and (local[0] / "cases.dump").read_bytes() == b"PGDMP-stub"
    assert [path for path, _, _ in seen.puts] == [f"/backups/ahrefs-cases/{local[0].name}.tar.gpg"]
    assert seen.messages == []


def test_backup_cries_when_the_copy_does_not_leave(
    tmp_path: Path, seen: _Seen, gnupg_home: Path
) -> None:
    """Q5: хранилище отказало (403, чужой ключ) — локальная копия цела, выход не нулём, алерт это называет.

    «Не снята локальная» и «снята, но не ушла наружу» — разные беды, и алерт
    обязан их различать: по первой восстанавливаться не из чего вовсе.
    """
    seen.refuse_puts = True
    done = _backup_sh(tmp_path, seen, gnupg_home)

    assert done.returncode != 0
    assert any(
        (path / "cases.dump").is_file()
        for path in (tmp_path / "backups").iterdir()
        if path.is_dir()
    )
    assert len(seen.messages) == 1
    assert "снята, внешняя НЕ отправлена" in seen.messages[0]


def test_backup_cries_when_there_is_nothing_to_dump(
    tmp_path: Path, seen: _Seen, gnupg_home: Path
) -> None:
    """Q6: postgres не запущен — бэкапа нет, алерт называет шаг, наружу ничего не ушло."""
    done = _backup_sh(tmp_path, seen, gnupg_home, postgres_up=False)

    assert done.returncode != 0
    assert seen.puts == []
    assert len(seen.messages) == 1
    assert "НЕ снят" in seen.messages[0] and "проверка стека" in seen.messages[0]


def test_notify_without_telegram_prints_instead_of_failing(
    tmp_path: Path, seen: _Seen, gnupg_home: Path
) -> None:
    """Q7: канал не настроен — текст в stderr с пометкой и ноль: бэкап не роняется из-за чата."""
    done = _run("notify.sh", "бэкап упал", env=_env(seen, gnupg_home, TELEGRAM_BOT_TOKEN=""))

    assert done.returncode == 0
    assert "НЕ отправлен" in done.stderr and "бэкап упал" in done.stderr
    assert seen.messages == []


def test_fetch_returns_what_push_sent(tmp_path: Path, seen: _Seen, gnupg_home: Path) -> None:
    """Q8: обратно приходит тот же каталог; неверный пароль — отказ словами и без каталога.

    Расшифровка идёт целиком до распаковки: испорченная копия не успевает
    наполовину распаковаться и выглядеть бэкапом.
    """
    backup = _backup(tmp_path)
    env = _env(seen, gnupg_home)
    assert _run("offsite_push.sh", str(backup), env=env).returncode == 0

    listed = _run("offsite_fetch.sh", "list", env=env)
    assert listed.stdout.split() == [f"{_STAMP}.tar.gpg"]

    fetched = _run("offsite_fetch.sh", "get", "latest", str(tmp_path / "back"), env=env)
    assert fetched.returncode == 0, fetched.stderr
    for name in ("cases.dump", "casedata.tar", "README.txt"):
        assert (tmp_path / "back" / _STAMP / name).read_bytes() == (backup / name).read_bytes()
    assert f"scripts/restore.sh {tmp_path / 'back' / _STAMP} --yes" in fetched.stdout

    wrong = _run(
        "offsite_fetch.sh",
        "get",
        "latest",
        str(tmp_path / "wrong"),
        env=_env(seen, gnupg_home, OFFSITE_PASSPHRASE="not-the-phrase"),
    )
    assert wrong.returncode != 0 and "не расшифровано" in wrong.stderr
    assert not (tmp_path / "wrong" / _STAMP).exists()
