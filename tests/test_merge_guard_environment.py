"""Гейт мержа судит код, а не окружение своего временного дерева.

`scripts/merge_guard.sh` гоняет гейты в одноразовом worktree, а в нём только
отслеживаемые файлы: `.venv` и `node_modules` лежат в `.gitignore`. Скрипт их
«одалживает» симлинками по списку каталогов. Список пришёл из канона под
раскладку `frontend/`, а фронт этого проекта — `web/`: `web/node_modules` не
одалживался, хук eslint (`cd web && npx --no-install eslint`) своего eslint не
находил, npx брал из своего кэша ESLint 10.11.0 вместо проектного 9.39.5, и тот
падал на загрузке конфига. Мерж блокировал дефект гейта, а не код (24.09.2026).

**Что проверяется:** настоящий `merge_guard.sh` на одноразовом репозитории с
раскладкой проекта. Каталоги фронта берутся из отслеживаемых `package.json`
САМОГО проекта, а не из списка в тесте (урок L123): появится второй фронт или
`web/` переедет — тест покраснеет раньше, чем гейт мержа.

**Чего НЕ проверяется, прямым текстом:** настоящие хуки. Вместо pre-commit стоит
заглушка, которая судит одно — видно ли в дереве, где она запущена, окружение,
без которого хуки берут чужой инструмент. Вопрос здесь не «чист ли код», а
«получил ли гейт то же окружение, что основной клон».
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_GUARD = _ROOT / "scripts" / "merge_guard.sh"
_MARK = "borrowed-marker"
#: Питоновская половина хуков зовёт `.venv/bin/python` буквально (четыре AST-хука)
#: и mypy через `LINT_VENV=.venv` — это соглашение проекта, а не догадка теста.
_PYTHON_ENV = ".venv"


def _own_env() -> dict[str, str]:
    """Окружение процесса без чужих настроек git и без переопределения списка гейта.

    `GIT_*` снимается: тест, запущенный из git-хука, унаследовал бы индекс
    настоящего репозитория. `MERGE_GUARD_BORROW` снимается: проверяется
    умолчание скрипта, а переменная подменила бы его целиком.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_", "MERGE_GUARD_")) and key not in {"DRY_RUN", "PYTHON"}
    }


def _polygon_env(bin_dir: Path) -> dict[str, str]:
    """Окружение полигона: вдобавок без глобального конфига git.

    Хуки и подпись коммитов разработчика полигону не нужны, а `bin_dir` с
    заглушкой pre-commit стоит в PATH первым.
    """
    env = _own_env()
    return env | {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "polygon",
        "GIT_AUTHOR_EMAIL": "polygon@example.invalid",
        "GIT_COMMITTER_NAME": "polygon",
        "GIT_COMMITTER_EMAIL": "polygon@example.invalid",
        "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    """git с причиной отказа в тексте падения, а не в выброшенном stderr."""
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=30
    )
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr.strip()}"
    return done.stdout


def _frontend_roots() -> list[Path]:
    """Каталоги отслеживаемых `package.json` проекта.

    npx ищет инструмент в `node_modules` ближайшего каталога с `package.json` —
    значит, именно их `node_modules` гейт мержа обязан одолжить.
    """
    listing = _git(_ROOT, _own_env(), "ls-files", "--", "*package.json").splitlines()
    roots = sorted({Path(p).parent for p in listing if Path(p).name == "package.json"})
    assert roots, "в проекте не нашлось ни одного package.json — тест смотрит не туда"
    return roots


def _polygon(repo: Path, env: dict[str, str], roots: list[Path], env_dirs: list[str]) -> None:
    """Репозиторий с раскладкой проекта: ветка `feature` поверх `main`.

    Окружение лежит так же, как в основном клоне: на диске есть, в git нет. Для
    этого `.gitignore` берётся настоящий — гейт мержа отказывается работать на
    грязном дереве, и полигон обязан быть чистым по тем же правилам.
    """
    repo.mkdir()
    _git(repo, env, "init", "-q", "-b", "main")
    shutil.copy(_ROOT / ".gitignore", repo / ".gitignore")
    (repo / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    for root in roots:
        (repo / root).mkdir(parents=True, exist_ok=True)
        (repo / root / "package.json").write_text("{}\n", encoding="utf-8")
    _git(repo, env, "add", "-A")
    _git(repo, env, "commit", "-q", "-m", "база")
    _git(repo, env, "switch", "-q", "-c", "feature")
    (repo / "change.txt").write_text("правка ветки\n", encoding="utf-8")
    _git(repo, env, "add", "change.txt")
    _git(repo, env, "commit", "-q", "-m", "правка")
    for d in env_dirs:
        (repo / d).mkdir(parents=True)
        (repo / d / _MARK).write_text("", encoding="utf-8")
    dirty = _git(repo, env, "status", "--porcelain")
    assert dirty == "", f"окружение полигона не спряталось в .gitignore:\n{dirty}"


def _pre_commit_stub(bin_dir: Path, ran_log: Path, env_dirs: list[str]) -> None:
    """Заглушка pre-commit: красная, если в дереве запуска не видно окружения.

    Каталог запуска пишется в журнал: без этого тест не отличил бы «гейт увидел
    окружение» от «гейт не запускался вовсе» — а пропуск merge_guard считает
    зелёным (выход 0 с пометкой ПРОПУЩЕН).
    """
    checks = [
        f"[ -e {shlex.quote(f'{d}/{_MARK}')} ] || {{ echo 'нет окружения: {d}'; missing=1; }}"
        for d in env_dirs
    ]
    lines = ["#!/usr/bin/env bash", f"pwd -P >> {shlex.quote(str(ran_log))}", "missing=0"]
    stub = bin_dir / "pre-commit"
    stub.write_text("\n".join([*lines, *checks, 'exit "$missing"']) + "\n", encoding="utf-8")
    stub.chmod(0o755)


def test_merge_worktree_gets_the_environment_of_every_frontend(tmp_path: Path) -> None:
    """Слитое дерево получает `node_modules` каждого фронта и `.venv` проекта.

    Падал до правки: умолчание `BORROW_DIRS` называло `frontend/node_modules`, а
    фронт проекта — `web/`, и заглушка отвечала «нет окружения: web/node_modules».
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env = _polygon_env(bin_dir)
    roots = _frontend_roots()
    env_dirs = [*((root / "node_modules").as_posix() for root in roots), _PYTHON_ENV]
    repo = tmp_path / "repo"
    _polygon(repo, env, roots, env_dirs)
    ran_log = tmp_path / "pre-commit-ran.log"
    _pre_commit_stub(bin_dir, ran_log, env_dirs)

    result = subprocess.run(
        ["bash", str(_GUARD), "feature", "main"],
        cwd=repo,
        env=env | {"DRY_RUN": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    report = f"{result.stdout}\n{result.stderr}"
    ran = ran_log.read_text(encoding="utf-8").splitlines() if ran_log.exists() else []
    assert len(ran) == 1, f"гейт pre-commit не запускался — судить нечего:\n{report}"
    assert Path(ran[0]) != repo.resolve(), (
        "pre-commit гонялся в клоне, а не во временном дереве — окружение там своё, "
        f"и тест ничего не доказывает:\n{report}"
    )
    assert result.returncode == 0, f"гейт мержа не дал хукам окружение проекта:\n{report}"
