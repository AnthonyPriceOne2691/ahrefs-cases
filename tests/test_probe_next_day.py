"""Вердикт пробника «назавтра»: правильный вывод из двух снимков.

Проверяется не запрос, а **толкование**: пробник говорит человеку, верно ли
правило кэша «закрытые месяцы неизменяемы». Ошибка здесь дороже отсутствия
инструмента — она подтвердит гипотезу, которая неверна, и неполные данные
останутся в базе навсегда, потому что повторный сбор их не перезапросит.

Сеть и база не нужны: сравнение — чистая функция над двумя словарями.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_next_day.py"
_EXIT_NOT_LIVE = 2


def _module() -> ModuleType:
    """Скрипт не пакет, поэтому импортируется по пути — как его запускает человек."""
    spec = importlib.util.spec_from_file_location("probe_next_day", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _module()


def _months_ago(months: int) -> str:
    """Первое число месяца, отстоящего от текущего на `months` назад."""
    anchor = datetime.now(UTC).date().replace(day=1)
    for _ in range(months):
        anchor = (anchor - timedelta(days=1)).replace(day=1)
    return anchor.isoformat()


def _snapshot(values: dict[str, float]) -> dict[str, Any]:
    return {"taken_at": "2026-09-12T10:00:00+00:00", "traffic": {"ahrefs.com": values}}


def test_changed_current_month_confirms_the_cache_rule(capsys: pytest.CaptureFixture[str]) -> None:
    """Меняется только текущий месяц — правило «до текущего неизменяемы» верно."""
    current_month, closed_month = _months_ago(0), _months_ago(1)
    probe._compare(
        _snapshot({closed_month: 100.0, current_month: 40.0}),
        _snapshot({closed_month: 100.0, current_month: 55.0}),
    )

    printed = capsys.readouterr().out
    assert "ПОДТВЕРЖДЕНА" in printed
    assert "ОПРОВЕРГНУТА" not in printed


def test_changed_closed_month_refutes_it(capsys: pytest.CaptureFixture[str]) -> None:
    """Дописанный закрытый месяц опровергает правило, даже если текущий тоже менялся.

    Приоритет именно такой: если Ahrefs дописывает закрытый месяц, то вывод
    «меняется только текущий» был бы неверным и успокоительным одновременно.
    """
    current_month, closed_month = _months_ago(0), _months_ago(1)
    probe._compare(
        _snapshot({closed_month: 100.0, current_month: 40.0}),
        _snapshot({closed_month: 118.0, current_month: 55.0}),
    )

    printed = capsys.readouterr().out
    assert "ОПРОВЕРГНУТА" in printed
    assert "closed_through" in printed


def test_nothing_changed_leaves_the_question_open(capsys: pytest.CaptureFixture[str]) -> None:
    """Совпавшие снимки не доказывают ничего — и пробник обязан это сказать.

    Соблазн прочитать «ничего не изменилось» как «правило верно» здесь и
    есть главная ошибка: сутки Ahrefs мог просто не пересчитывать домен.
    """
    current_month = _months_ago(0)
    probe._compare(_snapshot({current_month: 40.0}), _snapshot({current_month: 40.0}))

    printed = capsys.readouterr().out
    assert "остаётся открытым" in printed
    assert "ПОДТВЕРЖДЕНА" not in printed


def test_latest_snapshot_is_the_one_compared(tmp_path: Path) -> None:
    """Сравнивать надо с самым свежим снимком, а не с первым попавшимся."""
    for day, value in (("2026-09-12", 1.0), ("2026-09-13", 2.0)):
        (tmp_path / f"снимок-месяцев-{day}.json").write_text(
            json.dumps(_snapshot({"2026-09-01": value}), ensure_ascii=False), encoding="utf-8"
        )

    found = probe._previous_snapshot(tmp_path)

    assert found is not None
    path, payload = found
    assert path.name.endswith("2026-09-13.json")
    assert payload["traffic"]["ahrefs.com"]["2026-09-01"] == 2.0


def test_no_snapshot_yet_is_not_an_error(tmp_path: Path) -> None:
    """Первый запуск: сравнивать не с чем, и это штатный случай."""
    assert probe._previous_snapshot(tmp_path) is None


def test_fixture_mode_refuses_to_answer(tmp_path: Path) -> None:
    """На фикстуре пробник обязан отказаться, а не показать выдуманные числа.

    Фикстурный провайдер ответит собственной формулой — и снимок будет
    сравниваться сам с собой, подтверждая любую гипотезу.
    """
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "ahrefs.com", "--snapshot-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env={**os.environ, "AHREFS_PROVIDER": "fixture"},
    )

    assert result.returncode == _EXIT_NOT_LIVE
    assert "не live" in result.stderr
    assert not list(tmp_path.glob("*.json"))


def _quota(used: int) -> dict[str, int]:
    return {"units_limit_api_key": 2_000_000, "units_usage_api_key": used}


def _with_quota(used: int) -> dict[str, Any]:
    return {"taken_at": "2026-09-12T10:00:00+00:00", "quota": _quota(used), "traffic": {}}


def test_absolute_counter_is_not_an_answer(capsys: pytest.CaptureFixture[str]) -> None:
    """Первый снимок: счётчик ненулевой — и это ничего не значит.

    Первая редакция пробника считала ответом «счётчик больше потраченного» и на
    живом ключе напечатала «✓ обновился», хотя у ключа заказчика израсходовано
    полмиллиона независимо от наших запросов. Ошибка нашлась первым же живым
    запуском 13.09.2026.
    """
    probe._report_counter(_quota(532_476), None, 2_262)

    printed = capsys.readouterr().out
    assert "✓" not in printed
    assert "второй снимок" in printed


def test_motionless_counter_disarms_preflight(capsys: pytest.CaptureFixture[str]) -> None:
    """Счётчик не сдвинулся, а по журналу тратили — остаток из API верить нельзя."""
    probe._report_counter(_quota(530_812), _with_quota(530_812), 2_262)

    printed = capsys.readouterr().out
    assert "✗" in printed
    assert "не уменьшается" in printed


def test_moving_counter_names_the_gap_with_our_estimate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Сдвинулся — запросы тарифицируются; расхождение со сметой называется числом."""
    probe._report_counter(_quota(532_476), _with_quota(530_812), 2_262)

    printed = capsys.readouterr().out
    assert "✓" in printed
    assert "1664" in printed
    assert "завышает" in printed


def test_idle_period_proves_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """Ничего не тратили и ничего не сдвинулось — это не подтверждение."""
    probe._report_counter(_quota(530_812), _with_quota(530_812), 0)

    printed = capsys.readouterr().out
    assert "ничего не доказывает" in printed
    assert "✓" not in printed


def _pretend_live(monkeypatch: pytest.MonkeyPatch, snapshot: dict[str, Any]) -> None:
    """Пройти дальше отказа фикстуры, не трогая сеть: шов `_refuse_reason`."""

    async def _collect(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return snapshot

    monkeypatch.setattr(probe, "_refuse_reason", lambda: None)
    monkeypatch.setattr(probe, "_collect", _collect)


def test_quota_only_does_not_overwrite_the_day_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Дешёвая проверка не имеет права испортить дорогую.

    `--quota-only` не запрашивает месяцы. Запиши он снимок — он затёр бы полный
    снимок того же дня, и завтрашнее сравнение по H2 сравнивало бы пустоту.
    """
    full = tmp_path / f"{probe._SNAPSHOT_PREFIX}2026-09-13.json"
    full.write_text(json.dumps(_snapshot({"2026-09-01": 4_301_827.0})), encoding="utf-8")
    _pretend_live(monkeypatch, {"taken_at": "сейчас", "quota": _quota(532_476), "traffic": {}})

    code = probe._main(["ahrefs.com"], 3, tmp_path, quota_only=True)

    assert code == 0
    assert json.loads(full.read_text(encoding="utf-8"))["traffic"]["ahrefs.com"]
    assert sorted(p.name for p in tmp_path.glob("*.json")) == [full.name]


def test_full_run_writes_the_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Полный запуск снимок записывает — иначе сравнивать завтра будет нечего."""
    taken = {"taken_at": "сейчас", "quota": _quota(532_476), "traffic": {"ahrefs.com": {}}}
    _pretend_live(monkeypatch, taken)

    code = probe._main(["ahrefs.com"], 3, tmp_path, quota_only=False)

    assert code == 0
    written = list(tmp_path.glob("*.json"))
    assert len(written) == 1
    assert json.loads(written[0].read_text(encoding="utf-8"))["quota"] == _quota(532_476)
