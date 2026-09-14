"""Вердикт классификации: группа проекта с объяснением."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models._base import Base


class Verdict(Base):
    """Группа + score + причины по каждой метрике, привязанные к версии порогов.

    `score` отвечает на «какой из них лучше» и служит сортировкой внутри группы —
    по абсолютному приросту трафика: так выполняются оба ответа заказчика, и
    «рост ≥ X %» как порог, и «приоритет большему абсолютному числу» как порядок.
    """

    __tablename__ = "verdicts"
    __table_args__ = (
        UniqueConstraint("project_id", "ruleset_id", name="uq_verdict_project_ruleset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ruleset_id: Mapped[int] = mapped_column(
        ForeignKey("rulesets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    group: Mapped[Group] = mapped_column(Enum(Group, name="verdict_group"), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasons: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    """По каждой метрике: значение, порог, сработало или нет. Экран показывает
    именно это — «почему такая группа» должно отвечаться данными, а не догадкой."""

    point_a: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    point_b: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[MetricSource | None] = mapped_column(
        Enum(MetricSource, name="metric_source"), nullable=True
    )
    """По каким рядам посчитаны точки. Без него вердикт нельзя сверить ни с чем:
    числа таблицы кейса приходят отсюда, кривые — из серий, и совпадение этих
    двух миров держалось только на том, что человек звал `classify` и `cases` в
    одном режиме. На стенде, где по проекту лежат и живые, и фикстурные ряды,
    это дало кейс с таблицей «35 394 → 60 101» и кривой до 1 058 129 (Z10).

    `NULL` — вердикт, вынесенный до 14.09.2026, когда источник ещё не
    записывали. Не «фикстура по умолчанию»: часть таких вердиктов посчитана по
    живым рядам, и угадывание записало бы в базу неправду ровно там, где её
    убирают. Кейс по такому вердикту не собирается — переклассификация
    бесплатна и не делает ни одного запроса к Ahrefs."""

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
