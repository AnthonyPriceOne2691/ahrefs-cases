"""Проверенная строка списка — то, что готово стать проектом.

Отдельный тип между разбором и базой: приём обязан отчитаться до того, как
что-то записано (человек смотрит смету и число отказов, потом решает). Черновик
хранит `row_no`, чтобы отчёт и запись говорили об одной и той же строке файла.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ahrefs_cases.storage._enums import TargetMode


@dataclass(frozen=True, slots=True)
class ProjectDraft:
    """Поля §4 документа реализации, уже приведённые к типам.

    Ключ проекта — `(domain, target_mode, period_start)`, как в
    `UniqueConstraint` модели: один домен законно приходит дважды с разными
    периодами работ, и это два кейса, а не дубль.
    """

    row_no: int
    domain: str
    target_mode: TargetMode
    period_start: date
    period_end: date
    niche: str
    geo: str
    service_type: str
    client: str
    owner: str
    publishable: bool
    work_volume: int | None
    notes: str

    @property
    def key(self) -> tuple[str, TargetMode, date]:
        return (self.domain, self.target_mode, self.period_start)
