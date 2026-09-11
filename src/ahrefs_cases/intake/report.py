"""Отчёт о приёме списка: сколько принято, сколько отклонено и почему.

Отчёт — объект, а не печать в консоль. Его читают трое: тест (примеры B1, B5),
CLI-прогон и экран загрузки Ф6. Собери его строкой — и экрану пришлось бы
разбирать текст обратно.

Числа разделены намеренно. `accepted` — сколько строк годны; `created` и
`updated` — что с ними стало в базе. Одно число вместо трёх скрыло бы повторную
загрузку того же файла: она законна и должна выглядеть как «обновлено 93»,
а не «принято 93» второй раз.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ahrefs_cases.intake.rejections import Notice, Rejection, RejectReason


@dataclass(frozen=True, slots=True)
class IntakeReport:
    """Итог приёма одного источника."""

    origin: str
    accepted: int = 0
    created: int = 0
    updated: int = 0
    rejections: tuple[Rejection, ...] = field(default_factory=tuple)
    notices: tuple[Notice, ...] = field(default_factory=tuple)
    """Ячейки, которые не разобрали у **принятых** строк. Отдельным списком,
    потому что последствие другое: чинить их можно не торопясь, и на число
    отклонённых строк они не влияют."""

    @property
    def rejected_rows(self) -> int:
        """Строк отклонено — не отказов.

        У строки бывает три причины сразу (нет клиента, битая дата, кривой флаг);
        считать их тремя отклонёнными строками значит соврать в отчёте.
        """
        return len({rejection.row_no for rejection in self.rejections})

    def by_reason(self) -> dict[RejectReason, int]:
        """Сводка по причинам — то, что экран Ф6 показывает свёрнутым списком."""
        return dict(Counter(rejection.reason for rejection in self.rejections))

    def as_lines(self) -> list[str]:
        """Человеческий вид для CLI: сводка и первые строки с отказами."""
        lines = [
            f"источник: {self.origin}",
            f"принято: {self.accepted} (создано {self.created}, обновлено {self.updated})",
            f"отклонено строк: {self.rejected_rows}",
        ]
        lines.extend(
            f"  строка {rejection.row_no}: {rejection.field} — {rejection.reason.value}"
            + (f" ({rejection.detail})" if rejection.detail else "")
            for rejection in sorted(self.rejections, key=lambda item: (item.row_no, item.field))
        )
        if self.notices:
            # Свой раздел, а не общий список: смешать их значило бы показать
            # принятые строки в одном ряду с потерянными.
            lines.append(f"принято с замечаниями: {len({item.row_no for item in self.notices})}")
            lines.extend(
                f"  строка {notice.row_no}: {notice.field} — {notice.reason.value}"
                + (f" ({notice.detail})" if notice.detail else "")
                for notice in sorted(self.notices, key=lambda item: (item.row_no, item.field))
            )
        return lines
