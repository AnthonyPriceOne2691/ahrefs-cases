"""Источник рядов называет вызывающий — умолчания нет ни у кого.

Это оракул против **третьего** повторения урока L53. Дважды до этого выбор
источника подставлялся умолчанием — и оба раза в живом режиме сервис читал
пустоту: preflight сверял смету с фикстурной квотой, карточка проекта рисовала
пустые графики. На третий раз (12.09.2026) живой прогон собрал пять доменов, а
классификация объявила «данных не хватает» по всем.

Общее у трёх случаев одно: на фикстурах умолчание совпадает с истиной, поэтому
**ни один тест поймать это не может** — он и сам идёт на фикстурах. Ловится
только живым режимом или проверкой сигнатуры. Здесь — проверка сигнатуры.
"""

from __future__ import annotations

import inspect
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases import config
from ahrefs_cases.cases.builder import build_cases
from ahrefs_cases.classify.diagnose import diagnose_domain, diagnose_poor
from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import recalc
from ahrefs_cases.classify.rulesets import seed_thresholds
from ahrefs_cases.classify.verdicts import (
    classify_all,
    classify_project,
    classify_projects,
    compute_verdict,
)
from ahrefs_cases.cli.source import reading_source
from ahrefs_cases.storage._enums import Metric, MetricSource
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.verdict import Verdict

SERIES_READERS = [
    classify_all,
    classify_project,
    classify_projects,
    compute_verdict,
    preview,
    recalc,
    diagnose_poor,
    diagnose_domain,
    build_cases,
]


@pytest.mark.parametrize("reader", SERIES_READERS, ids=lambda f: f.__name__)
def test_source_has_no_default(reader: object) -> None:
    """У `source` нет значения по умолчанию: режим называет вызывающий.

    Умолчание здесь — не удобство, а тихий выбор за пользователя: код,
    написанный и проверенный на фикстурах, в бою продолжает читать фикстуры и
    сообщает «данных нет» вместо ответа.
    """
    parameter = inspect.signature(reader).parameters.get("source")  # type: ignore[arg-type]

    assert parameter is not None, "reader читает ряды — она обязана спрашивать источник"
    assert parameter.default is inspect.Parameter.empty, (
        f"у {reader.__name__} вернулось умолчание источника: "  # type: ignore[attr-defined]
        "на фикстурах оно совпадёт с истиной, в живом режиме — нет"
    )


def test_reading_source_prefers_the_caller_over_the_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E1, E2: названный источник сильнее режима провайдера, неназванный — слабее.

    Это и есть то различие, ради которого завели флаг: чтение уже купленного не
    обязано поднимать живой режим. Проверяется без базы и без сети — правило
    целиком укладывается в две ветки, и обе важны: вторая держит умолчание,
    которое трижды давало молчаливую пустоту (L53, L107).
    """
    from ahrefs_cases.cli.source import provider_source, reading_source

    monkeypatch.setattr(config.ahrefs, "provider", "fixture")
    assert reading_source(MetricSource.LIVE) is MetricSource.LIVE
    assert reading_source(None) is MetricSource.FIXTURE
    assert provider_source() is MetricSource.FIXTURE

    monkeypatch.setattr(config.ahrefs, "provider", "live")
    assert reading_source(MetricSource.FIXTURE) is MetricSource.FIXTURE
    assert reading_source(None) is MetricSource.LIVE


async def test_classify_by_named_source_does_not_need_the_live_mode(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E1: `classify --source live` при провайдере `fixture` считает по живым рядам.

    Ровно то, чего не хватало 14.09.2026: чтобы пересчитать вердикты по **уже
    купленным** живым рядам, приходилось поднимать живой режим — снимать
    предохранитель ради операции, которая ключом не пользуется (Z11).

    Оракул кладёт в базу ряды **двух** источников с разными числами: в одном
    источнике правильный выбор неотличим от неправильного (L107).
    """
    monkeypatch.setattr(config.ahrefs, "provider", "fixture")
    project = Project(
        domain="two-worlds.example",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 1),
        niche="fintech",
        geo="US",
        service_type="seo",
        client="Acme",
        owner="i.petrov",
        publishable=True,
        work_volume=10,
        notes="",
    )
    db_session.add(project)
    await db_session.flush()
    for source, value in ((MetricSource.FIXTURE, 100.0), (MetricSource.LIVE, 900_000.0)):
        for month in (date(2025, 1, 1), date(2025, 2, 1), date(2025, 11, 1), date(2025, 12, 1)):
            db_session.add(
                MetricPoint(
                    project_id=project.id,
                    metric=Metric.ORG_TRAFFIC,
                    point_date=month,
                    value=value,
                    source=source,
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
    ruleset = await seed_thresholds(db_session)

    await classify_project(db_session, project, ruleset, source=reading_source(MetricSource.LIVE))
    await db_session.flush()

    verdict = (await db_session.execute(select(Verdict))).scalars().one()
    assert verdict.source is MetricSource.LIVE
    assert verdict.point_b["values"]["org_traffic"] == 900_000.0
