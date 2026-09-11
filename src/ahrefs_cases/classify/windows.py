"""Окна точек для сбора: сколько месяцев истории покупать под точки А и Б.

Живёт в `classify`, потому что окна — часть **версии порогов**, а не настройка
процесса: пересчёт по новой версии обязан менять и то, что покупается. Отдать их
`collect` нельзя — контракт `layers` запрещает сбору знать про классификацию,
иначе классификация перестанет быть бесплатной и переигрываемой.

Модуль существует как **одно место** после того, как вызывающих стало двое.
Пока пороги читал только CLI, знание «окна берутся из активной версии» жило в
нём и читалось нормально. С Ф5 появился второй вход — очередь, — и он этого
знания не получил: прогон, запущенный кнопкой, покупал бесплатный максимум под
минимальную цену запроса, а прогон из консоли — окна порогов. Один и тот же
прогон под одним именем стоил и собирал разное (тот же механизм, что L53:
умолчание вызывающего отключает настройку, не трогая её).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.rulesets import active_ruleset, seed_thresholds, thresholds_of
from ahrefs_cases.collect.scheme import PointWindows


async def point_windows(session: AsyncSession) -> PointWindows:
    """Окна точек из активной версии порогов.

    Берётся **максимум** окон А и Б: покупаем одним размером, а считает каждая
    точка по своему окну. Разные размеры дали бы разную цену у двух запросов
    одного проекта и смету, которую нельзя объяснить одной строкой.
    """
    await seed_thresholds(session)
    windows = thresholds_of(await active_ruleset(session)).windows
    return PointWindows(
        point_months=max(windows.point_a_months, windows.point_b_months),
        baseline_months=windows.pre_start_baseline_months,
    )
