"""Коды возврата CLI. Пример приёмки: C15.

Единственный тест, запускающий скрипт как процесс: коды возврата и вывод в
stderr — это и есть его контракт, и проверить их вызовом функции нельзя.
Сеть и база здесь не нужны: все случаи отсекаются до подключения к чему-либо.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "run_collect.py"
_EXIT_BAD_SOURCE = 2


def _env_that_counts_the_child() -> dict[str, str]:
    """Окружение, в котором дочерний процесс тоже попадает в замер покрытия.

    Родительский `coverage` дочерний процесс не видит: считается только то, что
    исполнил он сам. Двенадцать тестов ниже гоняют настоящую команду, то есть
    исполняют CLI целиком, — а `cli/collect_commands.py` показывал 36 %, и ровно
    столько давал один импорт модуля. Гейт покрытия читал это как дыру в тестах
    и краснел на коде, который исполняется каждым прогоном (15.09.2026).

    Переменную читает хук `a1_coverage.pth` из site-packages и зовёт
    `coverage.process_startup()`. Ставим её ТОЛЬКО когда замер идёт: иначе
    обычный `pytest` начал бы сорить файлами `.coverage.*` в корне.
    """
    env = dict(os.environ)
    try:
        import coverage
    except ImportError:
        return env
    if coverage.Coverage.current() is not None:
        env["COVERAGE_PROCESS_START"] = str(_ROOT / "pyproject.toml")
    return env


def _cli_module() -> object:
    """CLI как модуль: `--only` разбирается до всякой сети и базы.

    Импорт по пути — скрипт не пакет; `sys.modules` заполняется до
    `exec_module`, иначе `@dataclass` внутри не находит собственный модуль.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_collect", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env=_env_that_counts_the_child(),
    )


@pytest.mark.parametrize(
    ("source", "expected_text"),
    [
        ("нет-такого.csv", "файл не найден"),
        ("список.pdf", "не понимаю источник"),
        ("https://example.com/list", "не понимаю источник"),
    ],
)
def test_unreadable_source_exits_with_two(source: str, expected_text: str) -> None:
    """C15: причина строкой в stderr и код 2 — не трассировка `io.open`.

    Опечатка в пути — самая частая ошибка запуска. Ответ трассировкой заставил
    бы человека читать стек ради строки «файла нет».
    """
    result = _run("intake", source)

    assert result.returncode == _EXIT_BAD_SOURCE
    assert expected_text in result.stderr
    assert "Traceback" not in result.stderr


def test_help_works_without_database() -> None:
    """`--help` не должен требовать ни базы, ни ключа: им пользуются до настройки."""
    result = _run("--help")

    assert result.returncode == 0
    assert "stage2" in result.stdout


def test_only_accepts_the_domain_as_a_human_typed_it() -> None:
    """E1/E2: `--only` приводит имя к канону тем же вызовом, что и приём.

    В базе лежит канонический хост, а человек набирает то, что видит в своём
    файле: `ПРОВЕРКА-Рост.example`, `WWW.Example.COM/path`. Прежде фильтр
    сравнивал строку как набрана и отвечал «в базе нет проектов» на проект,
    созданный минуту назад из того же файла.
    """
    module = _cli_module()

    assert module._only("WWW.Example.COM/path") == ["example.com"]
    assert module._only("Пример.Рф, example.org") == ["xn--e1afmkfd.xn--p1ai", "example.org"]


def test_only_refuses_what_is_not_a_domain() -> None:
    """E3: не-домен — отказ с причиной нормализатора, а не «в базе нет».

    Разница в том, что чинить: «не домен» чинится правкой команды, «в базе
    нет» — загрузкой списка. Один ответ на оба случая отправляет не туда.
    """
    module = _cli_module()

    with pytest.raises(module.OnlyNotADomainError, match="invalid_domain"):
        module._only("не домен вовсе")


def test_every_command_taking_a_domain_canonicalises_it() -> None:
    """L124 не должен вернуться через другую команду.

    `--only` починили первым, а `render`, `explain`, `diagnose` и `cases`
    сравнивали сырой ввод с каноном в базе ещё сутки: «проект не найден» на
    проект, который есть. Оракул смотрит на **текст вызова**, а не на поведение
    каждой команды: команд с доменом станет больше, и забывчивость повторится
    ровно в новой.
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    calls = [line.strip() for line in source.splitlines() if "args.domain" in line]

    assert calls, "команды с доменом должны существовать — иначе оракул проверяет пустоту"
    for call in calls:
        assert "_canonical(args.domain)" in call or "_named(args.domain)" in call, call


def test_every_paying_command_has_a_scope() -> None:
    """Платящая команда обязана уметь ограничиться названным списком.

    12.09.2026 живой прогон ушёл в Ahrefs за отладочными доменами стенда —
    `collect` получил `--only` (урок L111). `stage2` и `case-data` остались без
    него ещё на двое суток, хотя платят больше: шаг 2 — самая дорогая ступень.
    Оракул смотрит на разбор аргументов, поэтому поймает и следующую платящую
    команду, которой ещё нет.
    """
    # Разбор аргументов строится внутри `main`, поэтому читается исходник. Сам
    # импорт скрипта — тоже проверка: синтаксическая поломка нашлась бы иначе
    # только в бою.
    assert _cli_module() is not None

    source = _SCRIPT.read_text(encoding="utf-8")
    paying = ("collect_parser", "stage2_parser", "case_parser")
    scoped = source[source.index("--only") :]

    for name in paying:
        assert name in source, f"команда {name} исчезла — оракул проверяет пустоту"
    assert "for paying_parser in (stage2_parser, case_parser):" in scoped
    assert '"--only"' in scoped


def test_every_reading_command_takes_the_source() -> None:
    """Команда, которая только читает, обязана уметь взять источник флагом.

    Этот оракул был **обещан** поставкой `read-bought-series-without-live` и не
    написан: в её STATUS он стоит как `repro_test`, а в репозитории его нет.
    Ценой стал Z11 — флаг получили три команды, оказавшиеся под рукой, а
    считающие остались на режиме провайдера, и пересчёт вердиктов по уже
    купленным живым рядам снова требовал поднять живой режим.

    Поэтому проверяется **класс** команд, а не три имени: список читающих
    парсеров и наличие флага у каждого. Следующая читающая команда, забывшая
    флаг, покраснеет здесь.
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    reading = (
        "cases_parser",
        "render_parser",
        "pack_parser",
        "classify_parser",
        "recalc_parser",
        "preview_parser",
        "diagnose_parser",
        "explain_parser",
    )
    block = source[source.index("for reading_parser in (") :]
    block = block[: block.index('help="какие ряды читать')]

    for name in reading:
        assert name in block, f"читающая команда {name} осталась без --source (Z11, урок L142)"
    assert '"--source"' in source


def test_paying_commands_do_not_take_a_source() -> None:
    """У платящей команды выбора источника **нет**, и это не забывчивость.

    Она читает тем же режимом, которым покупает: выбрать фикстурные ряды и
    купить по ним живые данные значило бы записать точки под чужим именем — то
    есть сломать то самое различие, ради которого флаг заводили.
    """
    # Разбор аргументов строится внутри `main`, поэтому читается исходник. Сам
    # импорт скрипта — тоже проверка: синтаксическая поломка нашлась бы иначе
    # только в бою.
    assert _cli_module() is not None

    source = _SCRIPT.read_text(encoding="utf-8")
    block = source[source.index("for reading_parser in (") :]
    block = block[: block.index('help="какие ряды читать')]

    for name in ("collect_parser", "stage2_parser", "case_parser"):
        assert name in source, f"команда {name} исчезла — оракул проверяет пустоту"
        assert name not in block, (
            f"платящая команда {name} получила --source: покупка и пометка точек — один режим"
        )


def test_only_reads_the_domain_column_of_the_intake_file(tmp_path: Path) -> None:
    """Файл, которым делали `intake`, годится и для `--only`.

    Оператор загружает список файлом — это боевой сценарий, — и тот же файл
    естественно подставляет в прогон, чтобы он шёл ровно по нему. Раньше это
    отказывало на строке заголовков: «`domain,period_start,…`: не домен».
    Сообщение честное и бесполезное: человек видит свою же первую строку.

    Разделитель ищется, а не предполагается: агентство выгружает из Excel, и
    там бывает `;`.
    """
    module = _cli_module()
    comma = tmp_path / "список.csv"
    comma.write_text(
        "domain,period_start,niche\nWWW.Example.COM,2025-01-01,fintech\nsecond.example,2025-02-01,авто\n",
        encoding="utf-8",
    )
    semicolon = tmp_path / "из-excel.csv"
    semicolon.write_text("domain;period_start\nthird.example;2025-03-01\n", encoding="utf-8")

    assert module._only(str(comma)) == ["example.com", "second.example"]
    assert module._only(str(semicolon)) == ["third.example"]


def test_only_still_reads_a_plain_list_of_domains(tmp_path: Path) -> None:
    """Файл со строками-доменами читается как раньше — это тоже боевой ввод.

    Оракул стоит рядом с предыдущим нарочно: правило «в файле бывает колонка»
    не должно превратиться в «в файле обязана быть колонка».
    """
    module = _cli_module()
    plain = tmp_path / "домены.txt"
    plain.write_text("first.example\nsecond.example\n\n", encoding="utf-8")

    assert module._only(str(plain)) == ["first.example", "second.example"]
