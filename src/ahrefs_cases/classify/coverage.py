"""Хватает ли купленных месяцев под требования версии порогов.

Вопрос появился 11.09.2026 вместе с экономией сбора. Раньше история покупалась
с запасом «на всякий случай», и любая версия порогов считалась по данным,
которых заведомо хватало. Теперь запас до старта работ берётся ровно тот, что
просит версия порогов в момент **сбора**, а окно точки покупается до
минимальной стоимости запроса — и пересчёт по **другой** версии может попросить
месяцы, которых никто не покупал.

Цена молчания здесь высокая и неочевидная. Точка считается как среднее по тем
месяцам окна, которые в серии есть (`points._average`): отсутствующий месяц не
обнуляет значение, а просто не участвует. Это правильно для дыр в данных
Ahrefs, но для непокупленного месяца даёт вердикт, посчитанный по половине
окна, — и выглядит он ровно как настоящий. На калибровке, где вердикты
сравнивают с экспертной оценкой, такой вердикт объясняет расхождение неверно:
спорить будут с порогом, а виновата нехватка данных.

Модуль чистый: месяцы на входе, месяцы на выходе, ни базы, ни порогов из файла.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

from ahrefs_cases.classify import points as points_module
from ahrefs_cases.classify.thresholds import Windows


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """Каких месяцев не хватает проекту под эту версию порогов."""

    point_a: tuple[date, ...]
    point_b: tuple[date, ...]
    baseline: tuple[date, ...]

    @property
    def is_empty(self) -> bool:
        """Данных хватает: сообщать не о чем."""
        return not (self.point_a or self.point_b or self.baseline)

    @property
    def months(self) -> tuple[date, ...]:
        return tuple(sorted({*self.point_a, *self.point_b, *self.baseline}))

    def describe(self) -> str:
        """Чего не хватает — словами, с месяцами.

        Перечисление по частям, а не общим числом: «не хватает трёх месяцев» не
        говорит, чинить ли сбор (точка Б у свежего проекта) или включать
        baseline обратно. Это разные действия.
        """
        parts = [
            f"{name}: {', '.join(month.strftime('%Y-%m') for month in missing)}"
            for name, missing in (
                ("точка А", self.point_a),
                ("точка Б", self.point_b),
                ("baseline до старта", self.baseline),
            )
            if missing
        ]
        return "; ".join(parts)


def gap(
    months_present: Collection[date],
    *,
    period_start: date,
    period_end: date,
    windows: Windows,
) -> CoverageGap:
    """Что версия порогов просит и чего из этого **не покупали**.

    Месяцы берутся у `points`, а не считаются здесь заново: окно точки — правило
    предметной области, и второй его экземпляр разошёлся бы с первым при первой
    правке. Проверка обязана спрашивать ровно те месяцы, которые расчёт потом
    усреднит, иначе она проверяет не то.

    **Различаются два вида отсутствия, и это главное в модуле.** Месяц внутри
    собранного отрезка — дыра в данных Ahrefs: о ней уже судит правило
    достоверности серии, и вердикт `insufficient_data` по ней законен. Месяц за
    пределами отрезка — тот, который никто не покупал: судить по нему нечего, и
    вердикт выдавать нельзя.

    Пустая серия — не вопрос покрытия вовсе: у домена просто нет истории, и
    правильный ответ даёт классификация (`insufficient_data`), а не пропуск.
    Свалить эти случаи в один — значит потерять законный вердикт и показать
    заказчику «данных не хватает» там, где данных нет и не будет.

    Отсюда достижимый случай ровно один — месяцы **до** старта работ, которые
    просит `pre_start_baseline_months`: шаг 1 собирается историей, поэтому всё
    внутри периода куплено. Проект, собранный двумя точками, в эту проверку не
    попадает: у него не хватает середины периода, а это Z6, и судит о нём
    правило достоверности серии.
    """
    known = set(months_present)
    if not known:
        return CoverageGap(point_a=(), point_b=(), baseline=())

    first, last = min(known), max(known)

    def unbought(months: list[date]) -> tuple[date, ...]:
        return tuple(m for m in months if m not in known and (m < first or m > last))

    return CoverageGap(
        point_a=unbought(points_module.window_a(period_start, windows)),
        point_b=unbought(points_module.window_b(period_end, windows)),
        baseline=unbought(points_module.baseline_window(period_start, windows)),
    )
