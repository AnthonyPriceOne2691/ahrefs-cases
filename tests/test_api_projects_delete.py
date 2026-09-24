"""Удаление проекта: что уходит вместе с ним, что остаётся и когда нельзя.

Примеры приёмки поставки `project-deletion-api`: D1–D14 в её `spec.md`.

Всё на своих строках — домены `*.delete.example`, свои версии порогов, свои
люди: дев-база общая, и тест вправе удалять только созданное им (L80, L148).
Каталог выгрузки подменён временным: настоящие PDF стенда тест не видит.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import zipfile
from collections.abc import Awaitable, Callable, Iterator
from contextlib import AsyncExitStack
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from tests.owned_rows import delete_owned, drop_ruleset

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import (
    ArtifactFormat,
    Group,
    LedgerKind,
    Metric,
    MetricSource,
    RunItemOutcome,
    RunStatus,
    UserGroup,
)
from ahrefs_cases.storage import models as db
from ahrefs_cases.storage.locks import WORK_LOCK_KEY, work_lock
from ahrefs_cases.workers import jobs

PASSWORD = "очень-длинный-пароль"
GONE, KEEPER, ALSO_GONE = "gone.delete.example", "keeper.delete.example", "also-gone.delete.example"
VERSIONS = ("тест-удаление-1", "тест-удаление-2")
ENGINEER, CLERK, ADMIN = "del-engineer@test.local", "del-clerk@test.local", "del-adm@test.local"
GRANTED, REVOKED = "del-granted@test.local", "del-revoked@test.local"
PEOPLE: dict[str, tuple[UserGroup, dict[str, bool]]] = {
    ENGINEER: (UserGroup.ENGINEER, {}),
    CLERK: (UserGroup.USER, {}),
    ADMIN: (UserGroup.ADMIN, {}),
    GRANTED: (UserGroup.USER, {"delete_projects": True}),
    REVOKED: (UserGroup.ENGINEER, {"delete_projects": False}),
}
CAMPAIGNS = {"gone": (GONE, 2025), "twin": (GONE, 2024), "keeper": (KEEPER, 2025)}
"""Две кампании одного сайта и сосед, делящий с первой один PDF; у всех кейсы."""
ARTIFACTS = {"gone": ("own", "shared", "outside"), "twin": ("twin",), "keeper": ("shared",)}
JOURNAL = (("gone", RunItemOutcome.OK, 40), ("also_gone", RunItemOutcome.SKIPPED_NO_DATA, 0))
FIELDS = {"niche": "travel", "geo": "US", "service_type": "seo", "client": "Acme", "owner": "i.p"}
POINT = {"metric": Metric.ORG_TRAFFIC, "source": MetricSource.FIXTURE, "value": 1.0}
GONE_TRACE = {"domain": GONE, "metric_points": 3, "verdicts": 2, "cases": 1, "files": 1}
GONE_TRACE |= {"run_items": 1, "twin_campaigns": 1}

Ask = Callable[[AsyncSession], Awaitable[Any]]
Write = Callable[[Ask], list[Any]]


@pytest.fixture(scope="module")
def writer() -> Iterator[Write]:
    """Один цикл и движок на модуль — запись мимо приложения (уроки L51, L54)."""
    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Ask) -> list[Any]:
        async def _apply() -> list[Any]:
            async with AsyncSession(engine) as session:
                found = await action(session)
                await session.commit()
                return [found]

        return loop.run_until_complete(_apply())

    try:
        yield run
    finally:
        loop.run_until_complete(engine.dispose())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


@pytest.fixture(autouse=True)
def out_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    monkeypatch.setattr(config.export, "output_dir", tmp_path / "out")
    return tmp_path / "out"


def _pdf(path: Path, body: str) -> tuple[Path, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"%PDF-1.7 {body}".encode())
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


async def _cleanup(session: AsyncSession) -> None:
    await delete_owned(session, domains=(GONE, KEEPER, ALSO_GONE), emails=tuple(PEOPLE))
    for version in VERSIONS:
        await drop_ruleset(session, version)


def _project(domain: str, year: int) -> db.Project:
    return db.Project(
        domain=domain, period_start=date(year, 1, 1), period_end=date(year, 12, 1), **FIELDS
    )


def _artifact(case_id: int, file: tuple[Path, str]) -> db.CaseArtifact:
    path, digest = file
    row = db.CaseArtifact(case_id=case_id, path=str(path), filename=path.name, checksum=digest)
    row.fmt, row.built_at = ArtifactFormat.PDF, datetime.now(UTC)
    return row


async def _seed(session: AsyncSession, files: dict[str, tuple[Path, str]]) -> dict[str, int]:
    from ahrefs_cases.classify.thresholds import load_seed

    seed = load_seed().model_dump(mode="json")
    rulesets = [db.Ruleset(version=v, payload={**seed, "version": v}) for v in VERSIONS]
    hashed = security.hash_password(PASSWORD)
    people = {
        email: db.User(email=email, password_hash=hashed, group=group, permissions=personal)
        for email, (group, personal) in PEOPLE.items()
    }
    projects = {key: _project(*place) for key, place in CAMPAIGNS.items()}
    projects["also_gone"] = _project(ALSO_GONE, 2025)
    session.add_all([*rulesets, *people.values(), *projects.values()])
    await session.flush()
    ids = {key: project.id for key, project in projects.items()}
    for key, year in (("gone", 2025), ("twin", 2024)):
        for at in (date(year, month, 1) for month in (1, 2, 3)):
            session.add(db.MetricPoint(project_id=ids[key], point_date=at, **POINT))
    for key, names in ARTIFACTS.items():
        chosen, mine = rulesets[: 2 if key == "gone" else 1], {"project_id": ids[key]}
        verdicts = [db.Verdict(ruleset_id=r.id, group=Group.GOOD, **mine) for r in chosen]
        session.add_all(verdicts)
        await session.flush()
        case = db.Case(verdict_id=verdicts[0].id, **mine)
        session.add(case)
        await session.flush()
        session.add_all(_artifact(case.id, files[name]) for name in names)
    run = db.Run(started_by=people[ENGINEER].id, status=RunStatus.DONE, projects_total=3)
    run.projects_ok, run.units_actual = 2, 50
    session.add(run)
    await session.flush()
    for key, outcome, units in [*JOURNAL, ("twin", RunItemOutcome.OK, 10)]:
        item = db.RunItem(run_id=run.id, project_id=ids[key], outcome=outcome, units_actual=units)
        item.raw_domain = projects[key].domain
        session.add(item)
        if units:
            session.add(db.UnitsLedger(run_id=run.id, kind=LedgerKind.SPENT, units_actual=units))
    return {**ids, "run": run.id}


@pytest.fixture
def stand(migrated_db: None, writer: Write, out_dir: Path, tmp_path: Path) -> Iterator[Any]:
    """Проекты, кейсы, файлы, прогон и расход — свои, и убираются за собой."""
    files = {
        "own": _pdf(out_dir / f"{GONE} — Кейс v1.pdf", "своё"),
        "shared": _pdf(out_dir / "общий — Кейс v1.pdf", "общее"),
        "outside": _pdf(tmp_path / "elsewhere" / "gone.pdf", "чужой каталог"),
        "twin": _pdf(out_dir / f"{GONE} — Кейс v1 (2).pdf", "кампания 2024"),
    }
    writer(_cleanup)
    [ids] = writer(lambda session: _seed(session, files))
    yield SimpleNamespace(**ids, files={name: path for name, (path, _) in files.items()})
    writer(_cleanup)


@pytest.fixture
def client(stand: Any) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, email: str = ENGINEER) -> dict[str, str]:
    body = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


async def _rows(session: AsyncSession, project_id: int) -> dict[str, int]:
    """Строки проекта по таблицам — то, что обязан унести каскад."""
    count = select(func.count())
    artifacts = count.select_from(db.CaseArtifact).join(db.Case)
    owned = {
        "projects": count.where(db.Project.id == project_id),
        "points": count.where(db.MetricPoint.project_id == project_id),
        "verdicts": count.where(db.Verdict.project_id == project_id),
        "cases": count.where(db.Case.project_id == project_id),
        "artifacts": artifacts.where(db.Case.project_id == project_id),
    }
    return {name: int(await session.scalar(stmt) or 0) for name, stmt in owned.items()}


async def _journal(session: AsyncSession, run_id: int) -> tuple[Any, ...]:
    item, spent = db.RunItem, db.UnitsLedger
    items = select(item.raw_domain, item.units_actual, item.project_id).order_by(item.id)
    rows = (await session.execute(items.where(item.run_id == run_id))).all()
    total = select(func.count(), func.sum(spent.units_actual)).where(spent.run_id == run_id)
    return [tuple(row) for row in rows], tuple((await session.execute(total)).one())


def test_deletion_takes_what_the_project_owns_and_keeps_the_rest(
    client: TestClient, stand: Any, writer: Write
) -> None:
    """D1–D5: каскад уносит своё; журналы, вторая кампания и чужие файлы остаются."""
    [twin_before] = writer(lambda s: _rows(s, stand.twin))
    [(items, ledger)] = writer(lambda s: _journal(s, stand.run))

    response = client.delete(f"/api/projects/{stand.gone}", headers=_headers(client))

    assert response.status_code == 200
    assert response.json() == {"project_id": stand.gone, **GONE_TRACE, "pack_blocked": False}
    assert set(writer(lambda s: _rows(s, stand.gone))[0].values()) == {0}
    assert not stand.files["own"].exists(), "свой PDF стирается вместе с кейсом"
    assert stand.files["shared"].exists(), "D4: на общий файл ссылается кейс соседа"
    assert stand.files["outside"].exists(), "D5: вне каталога выгрузки удаление не хозяйничает"
    # D2: строка журнала та же, только без ссылки; расход не тронут (счётчики — D10).
    kept = [(*items[0][:2], None), *items[1:]]
    assert writer(lambda s: _journal(s, stand.run)) == [(kept, ledger)]
    # D3: у второй кампании сайта свои копии точек — они не уходят.
    assert writer(lambda s: _rows(s, stand.twin)) == [twin_before]
    assert stand.files["twin"].exists()

    second = client.delete(f"/api/projects/{stand.keeper}", headers=_headers(client))

    assert second.status_code == 200
    assert not stand.files["shared"].exists(), "D4: ничей файл уходит с последним кейсом"


@pytest.mark.parametrize(
    ("email", "allowed"), [(ADMIN, True), (CLERK, False), (GRANTED, True), (REVOKED, False)]
)
def test_deleting_is_a_right_of_its_own(
    client: TestClient, stand: Any, email: str, allowed: bool
) -> None:
    """D6: право по группе и лично — в обе стороны; `/me` отдаёт итог, а не набор группы."""
    headers = _headers(client, email)

    response = client.delete(f"/api/projects/{stand.gone}", headers=headers)

    assert response.status_code == (200 if allowed else 403)
    rights = client.get("/api/auth/me", headers=headers).json()["rights"]
    assert ("delete_projects" in rights) is allowed
    groups = client.get("/api/users/rights", headers=_headers(client)).json()["groups"]
    by_group = {name: "delete_projects" in groups[name] for name in groups}
    assert by_group == {"engineer": True, "admin": True, "user": False}


def test_missing_project_is_404(client: TestClient) -> None:
    """D7: отказ называет, чего нет."""
    response = client.delete("/api/projects/0", headers=_headers(client))

    assert (response.status_code, response.json()["detail"]) == (404, "проекта 0 нет")


def test_work_in_progress_refuses_deletion(client: TestClient, stand: Any, writer: Write) -> None:
    """D8, D9: идущий прогон и хвост задачи после его закрытия пишут строки проектов."""
    headers, gone = _headers(client), f"/api/projects/{stand.gone}"
    run = update(db.Run).where(db.Run.id == stand.run)
    writer(lambda s: s.execute(run.values(status=RunStatus.RUNNING)))
    loop, stack = asyncio.new_event_loop(), AsyncExitStack()
    try:
        by_run = client.delete(gone, headers=headers)
        writer(lambda s: s.execute(run.values(status=RunStatus.DONE)))
        loop.run_until_complete(stack.enter_async_context(work_lock()))
        by_tail = client.delete(gone, headers=headers)
    finally:
        loop.run_until_complete(stack.aclose())
        loop.close()

    assert (by_run.status_code, by_tail.status_code) == (409, 409)
    assert f"прогон {stand.run}" in by_run.json()["detail"]
    assert "через минуту" in by_tail.json()["detail"]
    assert writer(lambda s: _rows(s, stand.gone))[0]["points"] == 3
    assert client.delete(gone, headers=headers).status_code == 200


async def _work_is_free() -> bool:
    """Можно ли взять замок работы исключительно — из своего соединения."""
    engine = create_async_engine(config.storage.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            lock = text("SELECT pg_try_advisory_xact_lock(:key)")
            return bool(await connection.scalar(lock, {"key": WORK_LOCK_KEY}))
    finally:
        await engine.dispose()
        await asyncio.sleep(0)


def test_threshold_recalc_holds_the_work_lock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D9: пересчёт порогов пишет вердикты всех проектов — на это время замок его."""
    from ahrefs_cases.api.routers import rulesets

    seen: list[bool] = []

    async def _probe(*_args: object, **_kwargs: object) -> SimpleNamespace:
        seen.append(await _work_is_free())
        return SimpleNamespace(as_lines=lambda: ["пересчитано"])

    monkeypatch.setattr(rulesets, "recalc", _probe)

    response = client.post(f"/api/rulesets/{VERSIONS[0]}/recalc", headers=_headers(client))

    assert (response.status_code, seen) == (200, [False])


async def test_job_holds_the_work_lock_through_its_tail(
    needs_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D14: замок держится всю работу задачи — и хвост после закрытия прогона тоже."""

    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(jobs, "_finish", _noop)
    monkeypatch.setattr(jobs, "dispose_engine", _noop)
    seen: list[bool] = []

    async def work() -> str:
        seen.append(await _work_is_free())
        return "группы пересчитаны"

    await jobs._run_guarded(47, work())

    assert seen == [False]
    assert await _work_is_free(), "после задачи замок свободен"


def test_journal_keeps_each_deleted_project_apart(client: TestClient, stand: Any) -> None:
    """D10: удалённые проекты прогона не сливаются в одну судьбу с чужим доменом."""
    headers = _headers(client)
    for project in (stand.gone, stand.also_gone):
        assert client.delete(f"/api/projects/{project}", headers=headers).status_code == 200

    card = client.get(f"/api/runs/{stand.run}", headers=headers).json()

    fates = sorted(
        (fate["domain"], fate["outcome"], fate["units_actual"], fate["project_deleted"])
        for fate in card["fates"]
    )
    assert fates == [
        (ALSO_GONE, "skipped_no_data", 0, True),
        (GONE, "ok", 10, False),
        (GONE, "ok", 40, True),
    ]
    assert (card["projects_total"], card["projects_ok"], card["units_actual"]) == (3, 2, 50)


def _pack(path: Path, cases: list[Path], *, at: int) -> None:
    with zipfile.ZipFile(path, "w") as bundle:
        for case in cases:
            bundle.write(case, arcname=case.name)
        bundle.writestr("кейсы.csv", "домен;группа;файл\r\n")
    os.utime(path, (at, at))


def test_pack_with_a_deleted_case_waits_for_a_rebuild(
    client: TestClient, stand: Any, out_dir: Path
) -> None:
    """D11–D13: пачка опознаёт кейсы по содержимому и не отдаёт кейс удалённого."""
    headers, gone, files = _headers(client), f"/api/projects/{stand.gone}", stand.files
    _pack(out_dir / "кейсы-2026-09-24.zip", [files["own"], files["twin"]], at=1_758_000_000)
    assert client.get("/api/cases/pack", headers=headers).json()["outdated"] is None
    assert client.get("/api/cases/pack/download", headers=headers).status_code == 200

    preview = client.get(f"{gone}/deletion", headers=headers)

    assert preview.json() == {"project_id": stand.gone, **GONE_TRACE, "pack_blocked": True}
    assert files["own"].exists(), "предпросмотр ничего не удаляет"
    assert client.get(f"{gone}/deletion", headers=_headers(client, CLERK)).status_code == 403

    assert client.delete(gone, headers=headers).status_code == 200
    state = client.get("/api/cases/pack", headers=headers).json()
    refused = client.get("/api/cases/pack/download", headers=headers)

    assert (state["outdated"], refused.status_code) == ("project_deleted", 409)
    assert "пересоберите" in state["note"]
    assert refused.json()["detail"] == state["note"]

    _pack(out_dir / "кейсы-2026-09-25.zip", [files["twin"]], at=1_758_100_000)

    assert client.get("/api/cases/pack/download", headers=headers).status_code == 200
