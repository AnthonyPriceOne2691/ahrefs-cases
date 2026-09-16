"""Файл кейса объясняет сегодняшнюю группу — или честно называется устаревшим.

Примеры приёмки Z30: E1 (всё сходится), E2 (проекту кейс больше не положен),
E3 (вердикт пересчитан поверх — тот же `id`, другие числа), E4 (файл собран
другим расчётом), E5 (вердикта нет), E6 (округление не считается расхождением).

Найдено владельцем 16.09.2026 на `allthedifferences.com`: в карточке «плохой,
−99,9 %», а кнопка отдавала лист «+69 %», собранный по фикстурным рядам.
Формально всё сходилось — `Case.verdict_id` указывал на действующий вердикт:
вердикт пишется upsert'ом и при пересчёте сохраняет прежний `id`.
"""

from __future__ import annotations

from datetime import date

from ahrefs_cases.cases.freshness import case_mismatch
from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models.case import Case
from ahrefs_cases.storage.models.verdict import Verdict


def _case(verdict_id: int = 1, before: float = 44_083.5, after: float = 74_654.5) -> Case:
    return Case(
        id=10,
        project_id=5,
        verdict_id=verdict_id,
        version=24,
        highlights={
            "picked": [
                {
                    "subject": "org_traffic",
                    "before": before,
                    "after": after,
                    "pct": 69.3,
                    "label": "органический трафик",
                    "shown": "44 084 → 74 654 (+69 %)",
                }
            ]
        },
    )


def _verdict(
    group: Group = Group.MEDIUM,
    before: float = 44_083.5,
    after: float = 74_654.5,
    verdict_id: int = 1,
) -> Verdict:
    return Verdict(
        id=verdict_id,
        project_id=5,
        ruleset_id=1,
        group=group,
        score=1.0,
        reasons={"checks": []},
        point_a={"at": date(2023, 6, 1).isoformat(), "values": {"org_traffic": before}},
        point_b={"at": date(2024, 6, 1).isoformat(), "values": {"org_traffic": after}},
        source=MetricSource.LIVE,
    )


def test_file_and_screen_agree() -> None:
    """E1: числа те же, группа кейсовая — расхождения нет."""
    assert case_mismatch(_case(), _verdict()) is None


def test_group_is_no_longer_eligible() -> None:
    """E2: проект стал «плохим» — файл остался, но кейс этой группе не положен.

    Замер 16.09.2026: 51 проект из 62 с файлами оказался ровно в этом
    состоянии — вердикты пересчитали по живым рядам, файлы остались прежние.
    """
    assert case_mismatch(_case(), _verdict(group=Group.POOR)) == "group"


def test_numbers_changed_under_the_same_verdict_id() -> None:
    """E3: главный случай — тот же `id`, другие числа.

    Вердикт пишется upsert'ом по паре «проект + версия порогов»: пересчёт той
    же версией перезаписывает строку. Сверка по `verdict_id` тут молчит, и
    молчала: на экране «−99,9 %», в файле «+69 %».
    """
    stale = case_mismatch(_case(), _verdict(before=65_736.5, after=54.0))

    assert stale == "numbers"


def test_built_by_another_verdict() -> None:
    """E4: файл собран расчётом, которого больше нет среди действующих."""
    assert case_mismatch(_case(verdict_id=7), _verdict(verdict_id=9)) == "verdict"


def test_no_verdict_at_all() -> None:
    """E5: вердикта нет — объяснять файлу нечего."""
    assert case_mismatch(_case(), None) == "gone"


def test_rounding_is_not_a_divergence() -> None:
    """E6: страж от перегиба — тысячная доля величины расхождением не считается.

    Числа проходят через JSON и округление подписей. Оракул, требующий
    побитового равенства, объявил бы устаревшим каждый второй файл (урок L149).
    """
    assert case_mismatch(_case(after=74_654.5), _verdict(after=74_654.9)) is None
    assert case_mismatch(_case(after=74_654.5), _verdict(after=75_972.0)) == "numbers"
