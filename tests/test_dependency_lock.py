"""Зависимости Python ставятся из lock-файла — в образе и в CI (Z48).

24.09.2026 SQLAlchemy 2.1.0 вышел между двумя прогонами CI одной ветки и уронил
47 тестов (L223): зависимости были заданы только нижней границей, и сборка
ставила то, что вышло в тот день. Прод уцелел, потому что был собран часом
раньше. Теперь версии записаны в `uv.lock`, и проверки ниже держат три
обещания: lock называет каждую прямую зависимость и не спорит с манифестом;
образ и CI ставят из него — с хешами и с `--locked`, который роняет сборку на
устаревшем lock; версия uv одна у манифеста, образа и CI.

Это оракулы формы, как в `test_ci_gates_judge.py`: исполняет установку CI и
сборка образа, здесь — то, что можно проверить, не поднимая раннер.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _ROOT / "pyproject.toml"
_LOCK = _ROOT / "uv.lock"
_DOCKERFILE = _ROOT / "Dockerfile"
_QUALITY = _ROOT / ".github" / "workflows" / "quality.yml"

# Стадии образа на Python: боевая и дев-компоуза. Фронтовые ставят npm ci.
_PYTHON_STAGES = ("dev", "prod")
# Джобы CI, которые ставят зависимости продукта. `delivery` ставит только
# PyYAML для selftest канона — ветвь, которая в варианте D не исполняется.
_INSTALLING_JOBS = ("tests", "gates")


def _declared() -> list[Requirement]:
    project = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]
    lines = [*project["dependencies"], *project["optional-dependencies"]["dev"]]
    return [Requirement(line) for line in lines]


def _locked() -> dict[str, list[Version]]:
    """Имя пакета → записанные версии (при расщеплении по Python их бывает две)."""
    lock = tomllib.loads(_LOCK.read_text(encoding="utf-8"))
    found: dict[str, list[Version]] = {}
    for package in lock["package"]:
        found.setdefault(canonicalize_name(package["name"]), []).append(Version(package["version"]))
    return found


def _stages() -> dict[str, str]:
    """Стадия Dockerfile → её инструкции, продолжения строк склеены."""
    text = _DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    stages: dict[str, str] = {}
    name = ""
    for line in text.splitlines():
        head = re.match(r"FROM\s+\S+\s+AS\s+(\S+)", line, flags=re.IGNORECASE)
        if head:
            name = head.group(1)
            stages[name] = ""
        elif name and not line.lstrip().startswith("#"):
            stages[name] += line + "\n"
    return stages


def _jobs() -> dict[str, Any]:
    return yaml.safe_load(_QUALITY.read_text(encoding="utf-8"))["jobs"]


def _step(job: str, name: str) -> dict[str, Any]:
    steps = [step for step in _jobs()[job]["steps"] if step.get("name") == name]
    assert steps, f"в джобе {job} нет шага «{name}»"
    return steps[0]


def _pip_installs(text: str) -> list[str]:
    """Команды `pip install` шага; комментарии — не команды, в каноне их полно."""
    lines = (line.strip() for line in text.splitlines())
    return [line for line in lines if "pip install" in line and not line.startswith("#")]


def _installs_from_the_lock(where: str, text: str) -> None:
    """Общая форма установки из lock: перевод с `--locked`, pip с хешами, проект без deps."""
    assert "uv export --locked" in text, (
        f"{where}: зависимости не из lock — нет `uv export --locked`, который "
        "переводит uv.lock в список для pip и падает на устаревшем lock"
    )
    loose = [
        line
        for line in _pip_installs(text)
        if "--require-hashes" not in line and "--no-deps" not in line
    ]
    assert not loose, (
        f"{where}: pip ставит мимо lock-файла — {loose}. Зависимости — "
        "`pip install --require-hashes -r <экспорт>`, сам проект — `--no-deps`"
    )
    assert any("--require-hashes" in line for line in _pip_installs(text)), (
        f"{where}: список из lock ставится без `--require-hashes`"
    )


def test_every_declared_dependency_is_pinned_in_the_lock() -> None:
    """K1: каждая прямая зависимость записана, и запись не спорит с манифестом.

    Манифест правят, а lock пересобрать забывают — тогда `--locked` уронит
    сборку в CI. Здесь та же забывчивость ловится раньше, на локальном pytest,
    и с именем пакета. Граница проверяется, а не только имя: `sqlalchemy<2.1`
    держит `.distinct(expr)` в `collect/cache.py`, и lock с 2.1 её бы обошёл.
    """
    locked = _locked()
    missing = [str(req) for req in _declared() if canonicalize_name(req.name) not in locked]
    assert not missing, (
        f"в uv.lock нет: {missing} — pyproject.toml правили без пересборки lock; "
        "запусти scripts/lock_deps.sh и закоммить uv.lock"
    )
    conflicts = [
        f"{req} ← {version}"
        for req in _declared()
        for version in locked[canonicalize_name(req.name)]
        if version not in req.specifier
    ]
    assert not conflicts, f"записанная версия нарушает границу манифеста: {conflicts}"
    assert locked["sqlalchemy"] == [Version("2.0.54")], locked["sqlalchemy"]


def test_image_installs_only_from_the_lock() -> None:
    """K2: обе Python-стадии образа ставят зависимости из lock, проект — без deps."""
    stages = _stages()
    for stage in _PYTHON_STAGES:
        _installs_from_the_lock(f"Dockerfile, стадия {stage}", stages[stage])
    assert "--extra dev" in stages["dev"], "дев-стадия обязана ставить extras dev"
    assert "--extra dev" not in stages["prod"], "инструменты разработки уехали в боевой образ"


def test_ci_installs_only_from_the_lock() -> None:
    """K3: CI ставит тот же lock, что образ, и сверяет окружение `pip check`.

    В джобе гейтов ветка lock-файла стоит первой: канонные ветки ниже
    («requirements-dev.txt», «манифеста нет») ставят плавающие версии, и
    lock, проверенный после них, ничего бы не решал.
    """
    install = _step("tests", "Install")["run"]
    _installs_from_the_lock("CI, джоба tests", install)
    assert "pip check" in install

    gates = _step("gates", "Install backend deps")["run"]
    lock_branch = gates.split("elif [ -f requirements-dev.txt ]")[0]
    assert "if [ -f uv.lock ]" in lock_branch, "ветка lock-файла в гейтах не первая"
    _installs_from_the_lock("CI, джоба gates (ветка uv.lock)", lock_branch)
    assert "--no-deps -e ." in gates, "проект в venv гейтов ставится мимо lock"
    assert "pip check" in gates

    precommit = _step("gates", "pre-commit (all files, STRICT=1)")["run"]
    assert not _pip_installs(precommit), (
        "pre-commit ставится мимо lock — он есть в .venv из extras dev"
    )


def test_uv_is_one_version_for_the_manifest_the_image_and_ci() -> None:
    """K4: одна версия uv везде, где lock читают или пишут.

    Lock, записанный более новой uv, более старая может счесть устаревшим, и
    `--locked` уронит сборку без единой правки зависимостей — красный CI того
    же класса, что L223, только от инструмента.
    """
    uv_config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["tool"]["uv"]
    pinned = re.fullmatch(r"==(\S+)", uv_config["required-version"])
    assert pinned, "required-version обязан быть точной версией (==X.Y.Z)"
    version = pinned.group(1)

    image = re.search(
        r"^FROM ghcr\.io/astral-sh/uv:(\S+) AS uv$",
        _DOCKERFILE.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert image, "в Dockerfile нет стадии uv из официального образа"
    assert image.group(1) == version, f"uv образа {image.group(1)}, манифеста {version}"

    for job in _INSTALLING_JOBS:
        setups = [
            step
            for step in _jobs()[job]["steps"]
            if str(step.get("uses", "")).startswith("astral-sh/setup-uv@")
        ]
        assert len(setups) == 1, f"джоба {job}: setup-uv ожидается ровно один раз"
        assert str(setups[0]["with"]["version"]) == version, (
            f"джоба {job}: uv {setups[0]['with']['version']}, манифеста {version}"
        )
