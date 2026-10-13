"""Бриф проекта через API: каталог полей, правка, NDA и права.

Примеры приёмки поставки `brief-fields-api`: M18 (каталог виден читающим), M19
(специалист заполняет бриф, карточка его отдаёт), M20 (правка частичная, пустое
очищает), M21 (негодное поле — отказ словами, не пишется ничего), M22 (NDA —
это `publishable` наоборот), M23 (право `edit_briefs`: у всех групп, лично
отбирается). Поставки `brief-autofill`: M131, M133 (карточка знает по вердикту), M135
(«Кто подготовил» — сохранивший бриф), M136 (карточка и лист подставляют одно).
Поставки `brief-known-more`: M137 (кто подготовил — кто вёл), M139 (параллельные
услуги по базе), M143 (карточка и лист — одно и по новым пунктам).

Строки свои — проект `card.brief.example` и люди `*@brief.test.local`: дев-база
общая, тест убирает только созданное им (L80, L148).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.owned_rows import delete_owned

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.cases.builder import VerdictView, build_case
from ahrefs_cases.cases.parallel import parallel_services
from ahrefs_cases.classify.rulesets import active_ruleset
from ahrefs_cases.classify.series import load_series
from ahrefs_cases.export.brief_sheet import brief_sections
from ahrefs_cases.storage import Group, Metric, MetricSource, UserGroup
from ahrefs_cases.storage import models as db
from ahrefs_cases.storage.brief import FIELDS

PASSWORD = "очень-длинный-пароль"
DOMAIN = "card.brief.example"
CLERK, REVOKED = "clerk@brief.test.local", "revoked@brief.test.local"
ANNA = "anna@brief.test.local"
PEOPLE: dict[str, tuple[UserGroup, dict[str, bool]]] = {
    CLERK: (UserGroup.USER, {}),
    REVOKED: (UserGroup.ENGINEER, {"edit_briefs": False}),
    ANNA: (UserGroup.USER, {}),
}
NAMES = {ANNA: "Анна Петрова"}
"""Полное имя есть не у всех: у учётки без имени «Кто подготовил» — почта."""
DRIVE = "https://drive.google.com/drive/folders/brief-test"

Ask = Callable[[AsyncSession], Awaitable[Any]]


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Ask], Any]]:
    """Свой цикл и движок на модуль — запись мимо приложения, а его движок закрывает `lifespan`."""
    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Ask) -> Any:
        async def _apply() -> Any:
            async with AsyncSession(engine) as session:
                found = await action(session)
                await session.commit()
                return found

        return loop.run_until_complete(_apply())

    try:
        yield run
    finally:
        loop.run_until_complete(engine.dispose())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


async def _cleanup(session: AsyncSession) -> None:
    await delete_owned(session, domains=(DOMAIN,), emails=tuple(PEOPLE))


async def _seed(session: AsyncSession) -> int:
    hashed = security.hash_password(PASSWORD)
    session.add_all(
        db.User(
            email=email,
            full_name=NAMES.get(email, ""),
            password_hash=hashed,
            group=group,
            permissions=personal,
        )
        for email, (group, personal) in PEOPLE.items()
    )
    project = db.Project(
        domain=DOMAIN,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 1),
        niche="travel",
        geo="DE",
        service_type="seo",
        client="Acme",
        owner="i.p",
        publishable=True,
    )
    session.add(project)
    await session.flush()
    return project.id


@pytest.fixture
def project_id(migrated_db: None, writer: Callable[[Ask], Any]) -> Iterator[int]:
    writer(_cleanup)
    yield writer(_seed)
    writer(_cleanup)


def _point(at: str, traffic: float) -> dict[str, Any]:
    return {"at": at, "months_used": 3, "values": {"org_traffic": traffic}, "derived": {}}


@pytest.fixture
def verdict(project_id: int, writer: Callable[[Ask], Any]) -> None:
    """Вердикт «хороший» по действующей версии порогов: трафик в точке А — 2 487.

    Убирается с проектом: уборка сносит вердикты своих доменов.
    """

    async def _add(session: AsyncSession) -> None:
        ruleset = await active_ruleset(session)
        session.add(
            db.Verdict(
                project_id=project_id,
                ruleset_id=ruleset.id,
                group=Group.GOOD,
                score=2633.0,
                reasons={"checks": []},
                point_a=_point("2025-01-01", 2487.0),
                point_b=_point("2025-12-01", 5120.0),
                source=MetricSource.FIXTURE,
            )
        )

    writer(_add)


@pytest.fixture
def client(project_id: int, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, email: str = CLERK) -> dict[str, str]:
    body = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _patch(client: TestClient, project_id: int, body: dict[str, Any], email: str = CLERK) -> Any:
    return client.patch(
        f"/api/projects/{project_id}/brief", json=body, headers=_headers(client, email)
    )


def _card(client: TestClient, project_id: int) -> dict[str, Any]:
    response = client.get(f"/api/projects/{project_id}", headers=_headers(client))
    response.raise_for_status()
    return dict(response.json())


def test_catalog_is_open_to_readers(client: TestClient) -> None:
    """M18: каталог полей читает любая группа; без входа — 401, как всё остальное."""
    response = client.get("/api/brief-fields", headers=_headers(client))

    assert response.status_code == 200
    catalog = response.json()
    assert catalog["sections"][0] == "Инфо о сотруднике"
    by_key = {field["key"]: field for field in catalog["fields"]}
    assert "Очень высокая" in [choice["label"] for choice in by_key["complexity"]["choices"]]
    assert by_key["folder_url"]["column"] == "folder_url"
    assert client.get("/api/brief-fields").status_code == 401


def test_specialist_fills_the_brief(client: TestClient, project_id: int) -> None:
    """M19: группа user пишет бриф; пункт списка словами хранится ключом; карточка его отдаёт."""
    fields = {"client_request": "рост заявок", "site_type": "Маркетплейс", "folder_url": DRIVE}
    response = _patch(client, project_id, {"fields": fields})

    assert response.status_code == 200
    stored = {"client_request": "рост заявок", "site_type": "marketplace", "folder_url": DRIVE}
    signed = {**stored, "prepared_by": CLERK}
    assert response.json()["fields"] == signed  # M135
    assert _card(client, project_id)["brief"] == signed  # M135


def test_patch_is_partial_and_empty_clears(client: TestClient, project_id: int) -> None:
    """M20: не названное поле не трогается, пустая строка очищает названное."""
    _patch(client, project_id, {"fields": {"client_request": "рост", "goals": "топ-10"}})

    response = _patch(client, project_id, {"fields": {"client_request": ""}})

    assert response.status_code == 200
    assert _card(client, project_id)["brief"] == {"goals": "топ-10", "prepared_by": CLERK}  # M135


def test_bad_field_saves_nothing(client: TestClient, project_id: int) -> None:
    """M21: отказ называет каждое негодное поле подписью, а годные того же запроса не пишутся."""
    fields = {"goals": "рост", "complexity": "адская", "folder_url": "http://x", "nonsense": "1"}
    response = _patch(client, project_id, {"fields": fields})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Сложность проекта" in detail
    assert "Папка проекта на Google Drive" in detail
    assert "nonsense" in detail
    assert _card(client, project_id)["brief"] == {}


def test_nda_is_publishable_inverted(client: TestClient, project_id: int) -> None:
    """M22: флажок NDA пишет `publishable` наоборот — второго поля нет."""
    closed = _patch(client, project_id, {"nda": True})

    assert closed.json()["nda"] is True
    assert _card(client, project_id)["project"]["publishable"] is False

    _patch(client, project_id, {"nda": False})
    assert _card(client, project_id)["project"]["publishable"] is True


def test_edit_right_is_everyones_and_personal(client: TestClient, project_id: int) -> None:
    """M23: право у группы user есть; личное «Нет» его отбирает; чужой проект — 404."""
    rights = client.post("/api/auth/login", json={"email": CLERK, "password": PASSWORD})

    assert "edit_briefs" in rights.json()["rights"]
    assert _patch(client, project_id, {"nda": True}, email=REVOKED).status_code == 403
    assert _patch(client, 10**9, {"nda": True}).status_code == 404


def test_other_closes_service_and_project_kinds(client: TestClient, project_id: int) -> None:
    """M120: «Другое» — последний пункт «Тип услуги» и «Вид проекта»; пишется ключом `other`."""
    catalog = client.get("/api/brief-fields", headers=_headers(client)).json()
    by_key = {field["key"]: field for field in catalog["fields"]}
    other = {"service_kind": "Другое", "project_kind": "Другое"}
    response = _patch(client, project_id, {"fields": other})

    for key in other:
        assert by_key[key]["choices"][-1] == {"key": "other", "label": "Другое"}
    assert response.status_code == 200
    other_keys = {"service_kind": "other", "project_kind": "other"}
    assert response.json()["fields"] == {**other_keys, "prepared_by": CLERK}  # M135


def test_card_shows_what_the_file_knows(
    client: TestClient, project_id: int, writer: Callable[[Ask], Any]
) -> None:
    """M121: карточка отдаёт то, что лист подставляет у пустых пунктов; без вердикта — из файла."""

    async def _volume(session: AsyncSession) -> None:
        project = await session.get(db.Project, project_id)
        assert project is not None
        project.work_volume = 120

    from_file = {
        "department": "SEO (по услуге из файла)",
        "prepared_by": "i.p (вёл проект, из файла)",  # M137
        "service_kind": "Ежемесячное продвижение (период 12 мес.)",
        "topic": "Путешествия (по нише «travel»)",
        "dynamics_slice": "Весь период работ (по умолчанию)",
        "case_period_1": "01.2025 — 12.2025: SEO-продвижение (период и услуга из файла)",
    }
    assert _card(client, project_id)["brief_known"] == from_file  # M134
    writer(_volume)

    known = _card(client, project_id)["brief_known"]
    assert known == {**from_file, "budget": "120 (объём работ из файла)"}  # M134


def test_card_knows_what_the_verdict_tells(
    client: TestClient, verdict: None, project_id: int
) -> None:
    """M131: вид проекта — по трафику в точке А вердикта, тем же числом, что в таблице А → Б."""
    card = _card(client, project_id)
    known = card["brief_known"]

    assert card["verdict"]["comparison"][0]["before"] == 2487.0
    assert known["project_kind"] == "Рост существующего сайта (трафик на старте — 2\u00a0487)"
    assert known["result_weight"] == "Высокая (группа «хороший»)"  # M133


def test_card_and_sheet_substitute_the_same(
    client: TestClient, verdict: None, project_id: int, writer: Callable[[Ask], Any]
) -> None:
    """M136: у пустых пунктов карточка и лист PDF подставляют одно; заполненное — как записано."""
    _patch(client, project_id, {"fields": {"department": "pr", "goals": "топ-10"}})
    card = _card(client, project_id)

    async def _sheet(session: AsyncSession) -> dict[str, str]:
        project = await session.get(db.Project, project_id)
        stmt = select(db.Verdict).where(db.Verdict.project_id == project_id)
        found = (await session.execute(stmt)).scalars().one()
        assert project is not None
        case = build_case(project, VerdictView.of(found, "проверка"), {})
        return {row.label: row.value for section in brief_sections(case) for row in section.rows}

    rows = writer(_sheet)
    empty = [field for field in FIELDS if field.key not in card["brief"]]
    printed = {field.key: rows[field.label] for field in empty if rows[field.label]}

    assert printed == card["brief_known"]
    assert set(printed) == {
        "service_kind",
        "project_kind",
        "topic",
        "dynamics_slice",
        "case_period_1",
        "result_weight",
    }
    assert rows["Чей отдел вёл проект"] == "PR"
    assert "department" not in card["brief_known"]


def test_prepared_by_is_whoever_saved_the_brief(
    client: TestClient, project_id: int, caplog: pytest.LogCaptureFixture
) -> None:
    """M135: «Кто подготовил» пуст — пишется сохранивший; заполнен — не трогается; очищен — пуст."""
    with caplog.at_level(logging.INFO, logger="ahrefs_cases.api.routers.briefs"):
        first = _patch(client, project_id, {"fields": {"goals": "топ-10"}}, email=ANNA)
    [record] = [record for record in caplog.records if record.getMessage() == "brief_updated"]

    assert first.json()["fields"]["prepared_by"] == "Анна Петрова"
    assert record.signed == ["prepared_by"]
    assert "Анна Петрова" not in str(record.__dict__)

    _patch(client, project_id, {"fields": {"prepared_by": "Иван"}})
    kept = _patch(client, project_id, {"fields": {"goals": "топ-3"}}, email=ANNA)
    assert kept.json()["fields"]["prepared_by"] == "Иван"

    cleared = _patch(client, project_id, {"fields": {"prepared_by": ""}}, email=ANNA)
    assert "prepared_by" not in cleared.json()["fields"]
    assert "prepared_by" not in _card(client, project_id)["brief"]

    # M135: правка одного NDA или одни очистки пунктов информацию не готовят — подписи нет.
    nda_only = _patch(client, project_id, {"fields": {}, "nda": True}, email=ANNA)
    assert "prepared_by" not in nda_only.json()["fields"]
    clears_only = _patch(client, project_id, {"fields": {"goals": ""}}, email=ANNA)
    assert "prepared_by" not in clears_only.json()["fields"]


async def _twins(session: AsyncSession) -> None:
    """Тот же домен ещё трижды: линкбилдинг внахлёст, SEO внахлёст, PR после периода."""
    for service, start, end in (
        ("linkbuilding", date(2025, 6, 1), date(2026, 5, 1)),
        ("SEO ", date(2025, 3, 1), date(2025, 9, 1)),
        ("pr", date(2026, 2, 1), date(2026, 6, 1)),
    ):
        session.add(
            db.Project(
                domain=DOMAIN,
                period_start=start,
                period_end=end,
                niche="travel",
                geo="DE",
                service_type=service,
                client="Acme",
                owner="i.p",
                publishable=True,
            )
        )


def test_card_names_parallel_services_of_the_domain(
    client: TestClient, project_id: int, writer: Callable[[Ask], Any]
) -> None:
    """M139: проект того же домена с другой услугой внахлёст — в «Параллельно»; та же
    услуга («SEO » — тот же `seo`) и период без пересечения — нет."""
    assert "parallel_services" not in _card(client, project_id)["brief_known"]
    writer(_twins)

    known = _card(client, project_id)["brief_known"]

    assert known["parallel_services"] == "Линкбилдинг, 06.2025 — 05.2026 (тот же домен в базе)"


def _dated(at: str, traffic: float, rating: float) -> dict[str, Any]:
    return {
        "at": at,
        "months_used": 3,
        "values": {"org_traffic": traffic, "dr": rating},
        "derived": {},
    }


TRAFFIC_2025 = (1000, 1100, 1200, 900, 1000, 1100, 1200, 1300, 1400, 1450, 1500, 1500)
"""Ряд периода 01–12.2025: в 04.2025 трафик −25 % к марту, остальные месяцы — рост."""


def test_card_and_sheet_agree_on_the_new_items(
    client: TestClient, project_id: int, writer: Callable[[Ask], Any]
) -> None:
    """M143: просадка, падение DR, параллельный проект, YMYL и «вёл проект» — карточка
    (`brief_known`) и лист PDF печатают одно и то же по всем пунктам."""

    async def _setup(session: AsyncSession) -> None:
        project = await session.get(db.Project, project_id)
        assert project is not None
        project.niche = "финансы"
        ruleset = await active_ruleset(session)
        session.add(
            db.Verdict(
                project_id=project_id,
                ruleset_id=ruleset.id,
                group=Group.GOOD,
                score=1500.0,
                reasons={"checks": []},
                point_a=_dated("2025-01-01", 1000.0, 32.0),
                point_b=_dated("2025-12-01", 1500.0, 29.0),
                source=MetricSource.FIXTURE,
            )
        )
        session.add_all(
            db.MetricPoint(
                project_id=project_id,
                metric=Metric.ORG_TRAFFIC,
                point_date=date(2025, month, 1),
                value=float(value),
                source=MetricSource.FIXTURE,
                country="DE",
            )
            for month, value in enumerate(TRAFFIC_2025, start=1)
        )

    async def _sheet(session: AsyncSession) -> dict[str, str]:
        """Лист — тем же путём, что сборка (`builder._attempt`): ряды источника и пары домена."""
        project = await session.get(db.Project, project_id)
        stmt = select(db.Verdict).where(db.Verdict.project_id == project_id)
        found = (await session.execute(stmt)).scalars().one()
        assert project is not None
        series = await load_series(session, project_id, MetricSource.FIXTURE)
        case = replace(
            build_case(project, VerdictView.of(found, "проверка"), series),
            parallel=await parallel_services(session, project),
        )
        return {row.label: row.value for section in brief_sections(case) for row in section.rows}

    writer(_twins)
    writer(_setup)
    known = _card(client, project_id)["brief_known"]
    rows = writer(_sheet)

    printed = {field.key: rows[field.label] for field in FIELDS if rows[field.label]}
    assert printed == known
    assert known["difficulties"] == (  # M138
        "Просадка органического трафика в 04.2025: -25\u00a0% к 03.2025; "
        "Domain Rating снизился: 32 → 29 (по динамике Ahrefs — уточните причину)"
    )
    parallel = "Линкбилдинг, 06.2025 — 05.2026 (тот же домен в базе)"  # M139
    assert known["parallel_services"] == parallel
    assert known["features"] == (  # M140
        "YMYL-тематика: Google строже оценивает экспертность и надёжность сайта "
        "(по тематике «Финансы»)"
    )
    assert known["prepared_by"] == "i.p (вёл проект, из файла)"  # M137
