"""Гейт, который не судит, обязан быть виден — и не обязан быть зелёным.

15.09.2026 первый же прогон CI на диффе с Python-кодом вскрыл три дефекта одного
класса (Z18–Z20). Общее у них не механика, а исход: **оснастка отчитывалась
вместо того, чтобы судить**, и отчёт читался как вердикт.

* Z18: шаг покрытия стоял в джобе без Postgres, а сьют с 11.09 без дев-базы не
  стартует вовсе. Гейт был структурно красным на любом диффе с Python — и четыре
  дня этого никто не видел, потому что все диффы были без Python, и гейт честно
  печатал «изменённых prod-файлов нет».
* Z19: причину обрыва гейт отправлял в `/dev/null` и печатал «сьют не
  отработал?» — со знаком вопроса.
* Z20: мутационный гейт выходил нулём со словами «не могу определить, что
  мутировать»: конфиг лежал не там, где его читают, и под именем из mutmut 2.x.

Проверки ниже держат ровно это: сьют гоняется там, где у него есть база;
причина обрыва видна; область мутаций объявлена там, откуда её читают. Это
оракулы **формы** — они смотрят на оснастку, а не исполняют её. Так и задумано:
исполняет её CI, а форма — то единственное, что можно проверить, не поднимая
раннер.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_QUALITY = _ROOT / ".github" / "workflows" / "quality.yml"
_COVERAGE_GATE = _ROOT / "scripts" / "lint" / "check_diff_coverage.sh"


def _jobs() -> dict[str, Any]:
    return yaml.safe_load(_QUALITY.read_text(encoding="utf-8"))["jobs"]


def _runs(job: dict[str, Any]) -> list[str]:
    """Тексты всех `run:` джобы. Шаги-`uses` пропускаются: они ничего не зовут."""
    return [step["run"] for step in job.get("steps", []) if isinstance(step.get("run"), str)]


def _starts_the_suite(command: str) -> bool:
    """Команда поднимает полный сьют pytest.

    Две формы, и обе настоящие: прямой вызов `pytest` и гейт покрытия, который
    зовёт его внутри себя. Вторая — ровно тот случай, что дал Z18: в тексте
    шага слова `pytest` нет, а сьют он гоняет.
    """
    if "check_diff_coverage.sh" in command:
        return True
    return any(line.strip().startswith(("pytest", "python -m pytest")) for line in command.splitlines())


def test_suite_runner_job_has_a_database() -> None:
    """Джоба, поднимающая сьют, обязана иметь Postgres.

    Без него `tests/conftest.py::pytest_collection_modifyitems` останавливает
    прогон с `returncode=1`, и любой шаг, ждущий от сьюта результата, красный
    не по существу, а по месту, куда его поставили.
    """
    for name, job in _jobs().items():
        commands = [c for c in _runs(job) if _starts_the_suite(c)]
        if not commands:
            continue
        services = job.get("services") or {}
        assert "postgres" in services, (
            f"джоба '{name}' поднимает сьют, но не объявляет Postgres: "
            f"{commands[0].strip().splitlines()[0]}. "
            "Сьют без дев-базы останавливается — гейт будет красным структурно (Z18)"
        )


def test_the_suite_runs_once_per_workflow() -> None:
    """Сьют гоняется один раз за прогон, а покрытие берётся из его отчёта.

    Причина не в бюджете как таковом: второй прогон отвечает на тот же вопрос
    четырьмя лишними минутами. Шов для этого у гейта свой — `SKIP_TESTS=1`.
    """
    for name, job in _jobs().items():
        for step in job.get("steps", []):
            command = step.get("run")
            if not isinstance(command, str) or "check_diff_coverage.sh" not in command:
                continue
            env = step.get("env") or {}
            assert str(env.get("SKIP_TESTS")) == "1", (
                f"шаг покрытия в джобе '{name}' гоняет сьют сам — это второй прогон "
                "за тот же ответ. Отчёт делает шаг с pytest, гейт читает его при SKIP_TESTS=1"
            )


def test_coverage_gate_shows_why_the_suite_stopped() -> None:
    """Вывод сьюта сохраняется и печатается, когда отчёта нет.

    Знак вопроса в «сьют не отработал?» — признак того, что гейт выбросил
    ответ, который у него был (Z19).
    """
    text = _COVERAGE_GATE.read_text(encoding="utf-8")
    suite_call = [
        line for line in text.splitlines() if "-m pytest" in line and "--cov-report" in line
    ]
    assert suite_call, "в гейте покрытия не нашлось вызова сьюта — проверка смотрит не туда"
    assert not any(">/dev/null 2>&1" in line for line in suite_call), (
        "вывод сьюта уходит в /dev/null: причина обрыва пропадёт ровно там, "
        "где она нужна (Z19)"
    )
    missing = text.split("if [[ ! -f coverage.json ]]", 1)
    assert len(missing) == 2, "ветка «отчёта нет» в гейте покрытия не найдена"
    assert "tail -" in missing[1].split("fi", 1)[0], (
        "ветка «отчёта нет» не печатает хвост вывода сьюта — гейт снова будет "
        "спрашивать вместо того, чтобы отвечать (Z19)"
    )


def test_mutation_scope_is_declared_where_it_is_read() -> None:
    """Область мутаций объявлена в `src/`, ключом mutmut 3.x.

    `scripts/lint/mutation_py.sh` зовёт mutmut из корня импортов — каталога над
    пакетом, — и mutmut 3.x читает конфиг оттуда. Секция в корневом
    `pyproject.toml` не читается никем, а ключ `paths_to_mutate` — имя из 2.x:
    для 3.x это отсутствие настройки, и гейт честно отказывается судить (Z20).
    """
    src_config = _ROOT / "src" / "pyproject.toml"
    assert src_config.exists(), "нет src/pyproject.toml — mutmut не узнает, что мутировать (Z20)"
    scope = tomllib.loads(src_config.read_text(encoding="utf-8"))["tool"]["mutmut"]["source_paths"]
    assert scope == ["ahrefs_cases"], f"область мутаций не указывает на пакет: {scope}"

    root = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "mutmut" not in root.get("tool", {}), (
        "в корневом pyproject.toml снова появилась секция mutmut — оттуда её "
        "не читают, и она разойдётся с настоящей молча (Z20)"
    )


def test_the_coverage_waiver_expires_out_loud() -> None:
    """Отсрочка приговора живёт до названной даты, а не «пока».

    `continue-on-error` у судящего гейта — это waiver: гейт считает и печатает,
    но не блокирует. Такие отсрочки тихо становятся вечными — канон говорит про
    это прямо («правило без гейта живёт, пока его читают»). Здесь дата
    проставлена в самом workflow, и проверка ниже роняет сьют в тот день, когда
    срок вышел: waiver обязан кончиться громко.

    Красный от этой проверки чинится ДВУМЯ способами, и оба честные: закрыть
    долг тестами и убрать `continue-on-error`, либо продлить срок сознательно —
    новой датой и строкой в `docs/FINDINGS.md`, а не молчанием.
    """
    import datetime as _dt
    import re

    text = _QUALITY.read_text(encoding="utf-8")
    if "continue-on-error: true" not in text:
        return
    for name, job in _jobs().items():
        for step in job.get("steps", []):
            if not step.get("continue-on-error"):
                continue
            if "check_diff_coverage.sh" not in str(step.get("run", "")):
                continue
            deadline = re.search(r"срок (\d{2})\.(\d{2})\.(\d{4})", text)
            assert deadline, (
                f"шаг покрытия в джобе '{name}' не блокирует прогон, но срока не назвал. "
                "Waiver без даты — это отмена гейта, записанная как отсрочка"
            )
            day, month, year = (int(part) for part in deadline.groups())
            assert _dt.date.today() <= _dt.date(year, month, day), (
                f"срок отсрочки по покрытию CLI вышел {day:02d}.{month:02d}.{year}. "
                "Либо закрыть долг тестами и снять continue-on-error, либо назвать "
                "новый срок — здесь и в docs/FINDINGS.md (Z22)"
            )


def test_a_manifest_without_dependencies_is_not_a_dependency_decision() -> None:
    """Манифест с нулём зависимостей не требует объявления в STATUS.

    `check_new_dependency.py` считал появление манифеста решением о
    зависимостях. Посылка верна для `pyproject.toml` с двадцатью восемью
    пакетами и неверна для `src/pyproject.toml`, где нет ни одного: там только
    `[tool.mutmut]`, потому что mutmut 3.x читает конфиг из каталога запуска.
    Гейт требовал назвать зависимостью то, чего в файле нет, — требование без
    честного выхода (§4.3b). Адаптация записана в `scripts/lint/adapted.json`.
    """
    import sys

    sys.path.insert(0, str(_ROOT / "scripts" / "lint"))
    from dependency_manifests import extractor_for  # noqa: PLC0415

    extract = extractor_for("src/pyproject.toml")
    assert extract is not None, "pyproject.toml перестал считаться манифестом — проверка смотрит не туда"
    assert extract((_ROOT / "src" / "pyproject.toml").read_text(encoding="utf-8")) == set(), (
        "в src/pyproject.toml появились зависимости — тогда его и правда надо объявлять, "
        "а этот файл задуман только под область мутационного гейта"
    )
    assert extract((_ROOT / "pyproject.toml").read_text(encoding="utf-8")), (
        "в корневом pyproject.toml не нашлось зависимостей — извлекатель сломан, "
        "и гейт новых зависимостей молча пропустит любую"
    )
