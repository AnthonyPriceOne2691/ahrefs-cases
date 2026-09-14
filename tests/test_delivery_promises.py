"""Оракул, объявленный поставкой, обязан существовать.

Поставка называет в STATUS свой `repro_test` — тест, который падал до неё и
держит её результат после. Строка читается как гарантия, и ревью на неё
опирается: увидел имя — счёл вопрос закрытым.

14.09.2026 выяснилось, что гарантия может быть пустой. Поставка
`read-bought-series-without-live` объявила
`tests/test_cli_exit_codes.py::test_reading_commands_take_the_source_explicitly`,
а такого теста в репозитории нет и не было. Флаг `--source` работал, но класс
команд целиком остался без проверки — и половина команд осталась без флага (Z11).
Цена именно этого: не «тест не написан», а «вопрос считался закрытым».

`delivery_check` такого не ловит: он смотрит на формат STATUS, а не на то, куда
указывает имя. Оракул здесь, в тестах проекта, а не правкой канонного скрипта:
payload контура судит его владелец, и расхождение снимка с каноном стоило бы
дороже, чем собственная проверка.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DELIVERY = _ROOT / "delivery"
_DECLARED = re.compile(r"^- \*\*repro_test:\*\*\s*(.+?)\s*$", re.MULTILINE)
_CORRECTED = re.compile(r"^- \*\*repro_test_corrected:\*\*\s*(\S+::\S+)", re.MULTILINE)


def _target(value: str) -> str:
    """Адрес теста из строки STATUS: без пояснения в скобках и без `reason=`.

    Обе формы законны и встречаются в архиве: `путь::имя` и просто путь к файлу
    (у поставки, которую держит целый файл замеров). Пояснение рядом — тоже
    норма, и вырезать его надо здесь, а не требовать от людей писать голый
    адрес: гейт, спорящий с тем, как пишут, обходят, а не соблюдают.
    """
    value = re.split(r"\s+reason=", value, maxsplit=1)[0]
    return re.sub(r"\s*\(.*\)\s*$", "", value).strip()


def _resolves(target: str) -> bool:
    """Существует ли названный тест.

    У python-файла имя ищется определением (`def имя`), а не подстрокой:
    упоминание в докстроке соседнего теста — не тест. У фронтового файла имя
    теста — строка в `it(...)`, поэтому там достаточно вхождения. Адрес без
    `::` — обещание файлом целиком: проверяется его существование.
    """
    path, _, name = target.partition("::")
    file = _ROOT / path
    if not file.is_file():
        return False
    if not name:
        return True
    body = file.read_text(encoding="utf-8")
    if file.suffix == ".py":
        return re.search(rf"^\s*(async )?def {re.escape(name)}\b", body, re.MULTILINE) is not None
    return name in body


def test_every_declared_repro_test_exists() -> None:
    """У каждой поставки объявленный `repro_test` указывает на живой тест.

    Исключения два, оба названные. `n/a` с причиной — законное «репро нет»
    (не дефект, а недостающая возможность). Строка `repro_test_corrected` —
    поставка, чьё обещание не сдержали: исходная строка остаётся на месте как
    история, а рядом стоит тест, который написали вместо неё. Молча
    переписывать принятый STATUS нельзя: это ровно то «обновлено», которого
    не было.
    """
    broken: list[str] = []
    for status in sorted(_DELIVERY.rglob("STATUS.md")):
        text = status.read_text(encoding="utf-8")
        declared = _DECLARED.search(text)
        if declared is None:
            continue
        value = _target(declared.group(1))
        if value.startswith(("n/a", "none", "—")):
            continue
        if _resolves(value):
            continue
        corrected = _CORRECTED.search(text)
        if corrected is not None and _resolves(corrected.group(1)):
            continue
        broken.append(f"{status.relative_to(_ROOT)}: {value}")

    assert not broken, (
        "объявленный оракул не существует — строка STATUS обещает проверку, "
        "которой нет:\n" + "\n".join(broken)
    )
