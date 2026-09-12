"""Fixture-провайдер: те же ответы, что у живого, но без сети и без units.

Реализует `AhrefsProvider`. Единственное отличие от `AhrefsLive`, которое видно
снаружи, — `source=fixture` у точек и условные units в журнале. Всё остальное —
форма ответа, пропуски, пустая история — обязано вести себя одинаково, иначе
сквозной путь тестируется не тот, который поедет в прод.

Units считаются **по той же модели**, что применит live (`EndpointSpec.estimate_units`).
Считать их нулём было бы проще и вреднее: экран расхода и смета Ф2б
разрабатывались бы на нулях и «заработали» бы только в Ф7.
"""

from __future__ import annotations

from datetime import date

from ahrefs_cases.collect.endpoints import EndpointSpec
from ahrefs_cases.collect.fixtures.generator import generate_series
from ahrefs_cases.collect.fixtures.table import ScenarioTable, load_table
from ahrefs_cases.collect.provider import HistoryPoint, HistoryRequest, HistoryResult
from ahrefs_cases.storage._enums import MetricSource


class AhrefsFixture:
    """Синтетические серии по таблице сценариев."""

    source = MetricSource.FIXTURE

    def __init__(self, table: ScenarioTable | None = None) -> None:
        self._table = table or load_table()

    async def fetch_history(self, spec: EndpointSpec, request: HistoryRequest) -> HistoryResult:
        """История по одному endpoint'у. Сети здесь нет и быть не может."""
        scenario = self._table.scenario_for(request.target)
        # Якорь серии — конец **периода работ**, а не конец запрошенного окна:
        # иначе значение месяца зависело бы от того, каким окном его спросили,
        # и вердикт ехал бы вслед за схемой сбора (та выбирается по цене).
        anchor = request.period_end or request.date_to or date.today()  # noqa: DTZ011
        series = generate_series(request.target, scenario, seed=self._table.seed, end=anchor)

        wanted = set(spec.metrics.values())
        points = tuple(
            HistoryPoint(
                at=point.at,
                values={
                    metric: point.values[metric] for metric in wanted if metric in point.values
                },
            )
            for point in series
            if point.at >= request.date_from
            and (request.date_to is None or point.at <= request.date_to)
        )
        # Столько же строк, сколько отдаём: fixture обязан считать units по той
        # же формуле, что применит live, иначе смета проверяется на выдуманных
        # числах и «заработает» впервые на деньгах заказчика.
        units = spec.estimate_units(len(points)) if points else 0
        return HistoryResult(
            endpoint=spec.name,
            target=request.target,
            points=points,
            units_estimated=units,
            units_actual=units,
            source=self.source,
        )
