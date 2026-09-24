"""Бэкап проверяется восстановлением, а не чтением скрипта.

Соседний `test_backup_covers_state.py` судит ТЕКСТ: что том упомянут, что
есть строка про подтверждение. Это ловит удаление строки и потому не ноль,
но ступенью исполнения не считается: дамп нечитаемого формата, потерянная
таблица, `pg_restore`, спотыкающийся о расширение, — всё это пройдёт греп
и всплывёт в день, когда бэкап понадобится. В шапке `scripts/backup.sh`
это сказано словами: «бэкап, который ни разу не восстанавливали, бэкапом
не является». Здесь то же самое сказано механизмом.

**Что проверяется:** настоящий `scripts/backup.sh` снимает дамп, и этот
дамп восстанавливается настоящим `pg_restore` — тем же вызовом, что в
`scripts/restore.sh`.

**Чего НЕ проверяется, прямым текстом:** восстановление идёт в отдельную
базу, а не в рабочую. `restore.sh` делает `pg_restore --clean --if-exists`
по базе `cases` и стёр бы дев-окружение; тест, который сносит базу
разработчика, снимут после первого же запуска (§4.3b). Поэтому оркестровка
самого `restore.sh` — остановка сервисов, `casedata.tar`, старт обратно —
остаётся непокрытой, и это названо, а не спрятано.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE_DB = "cases_restore_probe"
_COMPOSE = os.getenv("COMPOSE", "docker compose -f docker-compose.dev.yml")


def _compose(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [*_COMPOSE.split(), *args],
        cwd=_ROOT,
        input=stdin,
        capture_output=True,
        check=False,
    )


def _stack_is_up() -> bool:
    """Нужны оба: postgres для дампа и api для артефактов кейсов.

    Проверяются оба, потому что `backup.sh` падает на втором так же, как на
    первом, а пропуск по одному лишь postgres читался бы как дефект бэкапа.
    """
    db = _compose("exec", "-T", "postgres", "psql", "-U", "cases", "-d", "cases", "-c", "select 1")
    api = _compose("exec", "-T", "api", "true")
    return db.returncode == 0 and api.returncode == 0


@pytest.fixture
def _scratch_db() -> object:
    """Отдельная база под восстановление: рабочую трогать нельзя.

    Пропуск без стека живёт здесь, а не в теле теста: фикстура исполняется
    раньше тела, и `createdb` без стека падал ассертом — задуманный пропуск
    становился ERROR. CI, где компоуз-стека нет вовсе, был красным на этом
    с 19.09.2026, хотя сам бэкап там ни разу не проверялся.
    """
    if not _stack_is_up():
        pytest.skip("дев-стек не поднят — восстанавливать неоткуда")
    _compose("exec", "-T", "postgres", "dropdb", "-U", "cases", "--if-exists", _PROBE_DB)
    created = _compose("exec", "-T", "postgres", "createdb", "-U", "cases", _PROBE_DB)
    assert created.returncode == 0, created.stderr.decode()
    yield
    _compose("exec", "-T", "postgres", "dropdb", "-U", "cases", "--if-exists", _PROBE_DB)


def _tables_in(db: str) -> set[str]:
    out = _compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "cases",
        "-d",
        db,
        "-t",
        "-A",
        "-c",
        "select tablename from pg_tables where schemaname='public' order by 1",
    )
    assert out.returncode == 0, out.stderr.decode()
    return {line for line in out.stdout.decode().split() if line}


@pytest.mark.slow
@pytest.mark.usefixtures("_scratch_db")
def test_the_dump_actually_restores(tmp_path: Path) -> None:
    made = subprocess.run(
        ["bash", str(_ROOT / "scripts" / "backup.sh")],
        cwd=_ROOT,
        env={**os.environ, "BACKUP_DIR": str(tmp_path), "KEEP": "1", "COMPOSE": _COMPOSE},
        capture_output=True,
        check=False,
    )
    assert made.returncode == 0, made.stderr.decode()

    dumps = sorted(tmp_path.rglob("cases.dump"))
    assert dumps, f"бэкап не создал дамп: {made.stdout.decode()}"

    restored = _compose(
        "exec",
        "-T",
        "postgres",
        "pg_restore",
        "-U",
        "cases",
        "-d",
        _PROBE_DB,
        "--clean",
        "--if-exists",
        stdin=dumps[0].read_bytes(),
    )
    # pg_restore возвращает 1 на предупреждениях о несуществующих объектах
    # при --clean на пустой базе; судим по результату, а не по коду.
    expected, got = _tables_in("cases"), _tables_in(_PROBE_DB)
    assert got == expected, (
        "восстановленная база отличается по составу таблиц.\n"
        f"нет в восстановленной: {sorted(expected - got)}\n"
        f"лишние: {sorted(got - expected)}\n"
        f"pg_restore: {restored.stderr.decode()[:400]}"
    )
