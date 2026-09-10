"""Журнал расхода units — то, чем объясняется счёт от Ahrefs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import LedgerKind
from ahrefs_cases.storage.models._base import Base


class UnitsLedger(Base):
    """Строка на каждый запрос к Ahrefs плюс строки-резервы.

    Резерв списывается при постановке прогона в очередь: следующее превью видит
    остаток минус резервы. Без этого «кнопка disabled при нехватке» защищает
    только первого нажавшего — а запускают шесть человек.

    Из этой же таблицы собирается «стоимость запуска на 100 URL», которую
    заказчик назвал метрикой успеха сервиса.
    """

    __tablename__ = "units_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[LedgerKind] = mapped_column(Enum(LedgerKind, name="ledger_kind"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    target: Mapped[str] = mapped_column(String(253), nullable=False, default="")

    units_estimated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_per_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """Значения заголовков `x-api-units-cost-total`, `-total-actual`, `-row`.
    Логируются с первого запроса: расчёты по докам расходятся с реальностью, а
    объяснять счёт придётся."""

    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
