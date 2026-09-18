"""Всё состояние, переживающее контейнер, попадает в бэкап.

Инвариант не про скрипт, а про **соответствие двух файлов**: том появляется в
`docker-compose.yml`, а помнить про него должен `scripts/backup.sh`. Забыть —
легко: том добавляют ради одной фичи, бэкап трогают раз в полгода, и узнают об
этом в день восстановления.

Поэтому список томов берётся из компоуза, а не переписывается сюда: переписанный
список разошёлся бы с настоящим ровно тогда, когда появился бы новый том.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_COMPOSE = _ROOT / "docker-compose.yml"
_BACKUP = _ROOT / "scripts" / "backup.sh"
_RESTORE = _ROOT / "scripts" / "restore.sh"

_REPRODUCIBLE = {
    # Очередь: задачи пересобираются запуском прогона, а недоделанная задача из
    # вчерашнего бэкапа хуже её отсутствия — она потратит units повторно.
    "redisdata",
}


def _volumes() -> set[str]:
    compose = yaml.safe_load(_COMPOSE.read_text(encoding="utf-8"))
    return set(compose.get("volumes") or {})


def test_every_stateful_volume_is_named_in_the_backup() -> None:
    """E1: новый том обязан попасть в бэкап или быть объявлен пересобираемым.

    Если тест покраснел из-за нового тома — решение принимается здесь и один
    раз: либо строка в `scripts/backup.sh`, либо запись в `_REPRODUCIBLE` с
    причиной, почему это состояние не жалко.
    """
    script = _BACKUP.read_text(encoding="utf-8")

    forgotten = {volume for volume in _volumes() - _REPRODUCIBLE if volume not in script}

    assert not forgotten, f"тома есть в компоузе, но не в бэкапе: {', '.join(sorted(forgotten))}"


def test_the_reproducible_volume_is_skipped_on_purpose() -> None:
    """Пропуск объявлен, а не случаен: причина написана в самом скрипте.

    «Не бэкапим» без причины через полгода читается как «забыли», и следующий
    инженер добавит том в бэкап, восстановив однажды чужую очередь поверх
    свежей.
    """
    script = _BACKUP.read_text(encoding="utf-8")

    for volume in _REPRODUCIBLE:
        assert volume in script, f"{volume} не бэкапится — это должно быть сказано в скрипте"


def test_restore_needs_an_explicit_confirmation() -> None:
    """E3: восстановление затирает базу, поэтому оно не делается «по умолчанию».

    Подтверждение аргументом, а не вопросом в терминале: восстанавливают в
    плохой день, часто по ssh из скрипта, где интерактивного ответа не будет.
    """
    script = _RESTORE.read_text(encoding="utf-8")

    assert '"$CONFIRM" != "--yes"' in script
    assert "exit 0" in script


def test_backup_refuses_without_a_running_database() -> None:
    """E2: без запущенного postgres бэкап не снимается.

    Пустой архив — худший исход: он выглядит как бэкап и обнаруживается в день
    восстановления.
    """
    script = _BACKUP.read_text(encoding="utf-8")

    assert "не запущен" in script
    assert "exit 1" in script


def test_scripts_are_executable() -> None:
    """Скрипт без бита запуска ставится в cron и молча не работает."""
    for script in (_BACKUP, _RESTORE):
        assert script.stat().st_mode & 0o111, f"{script.name} не исполняемый"


def test_a_failed_dump_cannot_destroy_the_previous_backup() -> None:
    """Бэкап собирается в стороне и переименовывается готовым.

    `> "$TARGET/cases.dump"` обрезает файл до того, как pg_dump скажет хоть
    слово: упавший дамп затёр бы хороший бэкап, снятый в ту же минуту, и
    ротация успела бы посчитать огрызок за копию.
    """
    script = _BACKUP.read_text(encoding="utf-8")

    assert 'PARTIAL="$TARGET.partial"' in script
    assert 'mv "$PARTIAL" "$TARGET"' in script
    assert "trap " in script


def test_rotation_does_not_need_bash_four() -> None:
    """Ротация работает и на bash 3.2 — том, что лежит в /bin на macOS.

    Первый живой запуск упал именно здесь: `mapfile` не нашёлся уже **после**
    того, как архив был снят. Скрипт напечатал «снято», вернул 127 и оставил
    ротацию несделанной — в cron это выглядит как работающий бэкап.
    """
    commands = [
        line.strip()
        for line in _BACKUP.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("#")
    ]

    # Проверяются **команды**, а не текст файла: слово `mapfile` осталось в
    # комментарии, объясняющем, почему его здесь нет.
    assert not [line for line in commands if line.startswith("mapfile")]
    assert any("while IFS= read -r old" in line for line in commands)
