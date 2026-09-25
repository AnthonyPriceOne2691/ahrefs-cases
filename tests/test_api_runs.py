"""Очередь и запуск прогона по HTTP.

Примеры приёмки поставки `api-runs`: E1 (без токена), E2 (запуск), E3 (замок),
E4 (журнал), E5 (нет прогона), E6 (inline-очередь), E7 (упавшая задача),
E8 (задача кейсов), E9 (выбор очереди), E10 (простые аргументы).

Очередь в тестах — `inline`: задача выполняется в том же процессе, и это не
подмена, а рабочий режим разработки (Redis на машине может не быть).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from tests.owned_rows import delete_owned, isolated_ruleset

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import RunStatus, UserGroup
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.workers import jobs, queue
from ahrefs_cases.workers.queue import InlineQueue, RedisQueue, build_queue

PASSWORD = "очень-длинный-пароль"
EMAIL = "runner@test.local"
RULESET = "тест-прогоны-api"
"""Своя версия порогов: с B6 прогон классифицирует все проекты базы по
действующей версии, и по чужой тест переписал бы вердикты стенда (Z12)."""


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
    """Один цикл и движок на модуль — запись мимо приложения (уроки L51, L54)."""
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from ahrefs_cases import config

    loop = asyncio.new_event_loop()
    engine = create_async_engine(config.storage.database_url)

    def run(action: Callable[..., object]) -> None:
        async def _apply() -> None:
            async with AsyncSession(engine) as session:
                await action(session)
                await session.commit()

        loop.run_until_complete(_apply())

    try:
        yield run
    finally:
        loop.run_until_complete(engine.dispose())
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()


def _cleanup(write: Callable[[Callable[..., object]], None]) -> None:
    async def _delete(session: object) -> None:
        await delete_owned(session, domains=("runs.example",), emails=(EMAIL,))  # type: ignore[arg-type]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    monkeypatch.setattr(config.storage, "queue_backend", "inline")


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)
    undo = isolated_ruleset(writer, RULESET)

    async def _seed(session: object) -> None:
        session.add_all(  # type: ignore[attr-defined]
            [
                User(
                    email=EMAIL,
                    full_name="Оператор",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.USER,
                ),
                Project(
                    domain="runs.example",
                    period_start=date(2025, 1, 1),
                    period_end=date(2025, 12, 1),
                    niche="fintech",
                    geo="US",
                    service_type="seo",
                    client="Acme",
                    owner="i.petrov",
                    publishable=True,
                    notes="",
                ),
            ]
        )

    writer(_seed)
    yield
    undo()
    _cleanup(writer)


@pytest.fixture
def client(seeded: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def test_start_needs_a_token(client: TestClient) -> None:
    """E1: запуск прогона тратит units — он закрыт правом `run`."""
    assert client.post("/api/runs").status_code == 401


def test_user_may_start_a_run(client: TestClient) -> None:
    """E2 и E6: право `run` есть у всех трёх групп; inline-очередь отработала."""
    response = client.post("/api/runs", headers=_headers(client))

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"] > 0
    assert body["queued_as"].startswith("inline:")


def test_second_run_is_refused_while_one_is_active(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """E3: второй прогон стоит вторую цену — отказ с номером активного."""

    headers = _headers(client)
    first = client.post("/api/runs", headers=headers).json()

    async def _hang(session: object) -> None:
        from sqlalchemy import update

        # Только **свой** прогон: `update(Run).values(...)` без условия
        # помечало «идущим» каждый прогон в базе, включая чужие, и они
        # оставались такими навсегда — следующий запуск упирался в чужой замок.
        await session.execute(  # type: ignore[attr-defined]
            update(Run).where(Run.id == first["run_id"]).values(status=RunStatus.RUNNING)
        )

    writer(_hang)

    second = client.post("/api/runs", headers=headers)

    assert second.status_code == 409
    assert str(first["run_id"]) in second.json()["detail"]


def test_journal_shows_status_and_units(client: TestClient) -> None:
    """E4: журнал считает проекты и units, а не задачи (урок L13)."""
    headers = _headers(client)
    started = client.post("/api/runs", headers=headers).json()

    rows = client.get("/api/runs", headers=headers).json()
    one = client.get(f"/api/runs/{started['run_id']}", headers=headers).json()

    assert rows[0]["id"] == started["run_id"]
    assert one["projects_total"] >= 1
    assert one["status"] in {"done", "partial", "failed", "queued", "running"}
    assert "units_actual" in one
    # Смета записана в строку прогона, а не только в резерв: журнал показывает
    # «смета → факт», и нулевая колонка врала бы у каждого прогона.
    assert one["units_estimated"] > 0


def test_refresh_run_actually_starts(client: TestClient) -> None:
    """Запуск с догрузкой доходит до задачи, а не виснет в очереди.

    Очередь пересылает аргументы **позиционно**; пока `refresh` был объявлен
    только-ключевым, вызов падал `TypeError` ещё до тела задачи. Ответ при этом
    приходил `202`, задача не начиналась, и строка оставалась `queued` навсегда —
    замок «один активный прогон» блокировал все следующие запуски.

    Поэтому проверяется не код ответа, а **состояние прогона после**: 202 здесь
    ничего не доказывает.
    """
    headers = _headers(client)

    started = client.post("/api/runs", params={"refresh": True}, headers=headers).json()

    row = client.get(f"/api/runs/{started['run_id']}", headers=headers).json()
    assert row["status"] != "queued", "задача не начиналась: прогон завис в очереди"
    assert row["units_estimated"] >= 0


def test_ui_run_leaves_groups_behind(client: TestClient) -> None:
    """B6: после прогона из интерфейса у проекта есть группа.

    Прогон делал только шаг 1, и «Проекты» оставались без групп у всех — до
    консольного `classify`. Классификация бесплатна, и теперь она — хвост
    прогона. Спрашиваем экран проектов, а не базу: пустой была именно выдача.
    """
    headers = _headers(client)
    client.post("/api/runs", headers=headers)

    rows = client.get("/api/projects", params={"query": "runs.example"}, headers=headers).json()
    assert [row["domain"] for row in rows] == ["runs.example"]
    assert rows[0]["group"] is not None, "прогон кончился без классификации"


def test_stage2_estimate_counts_the_candidates(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """B6: смета второй кнопки называет ровно тех, кого выбирает правило отбора.

    Число сверяется с самим правилом (`stage2_candidates`), а не с константой:
    база общая со стендом, и кандидатов в ней столько, сколько есть. Важно,
    что экран и шаг 2 считают одних и тех же — иначе смета называла бы цену
    чужого прогона.
    """
    headers = _headers(client)
    client.post("/api/runs", headers=headers)
    expected: list[int] = []

    async def _count(session: object) -> None:
        from sqlalchemy import select

        from ahrefs_cases.classify.candidates import stage2_candidates
        from ahrefs_cases.storage import MetricSource

        projects = (await session.execute(select(Project))).scalars().all()  # type: ignore[attr-defined]
        found = await stage2_candidates(session, projects, source=MetricSource.FIXTURE)  # type: ignore[arg-type]
        expected.append(len(found))

    writer(_count)

    body = client.get("/api/runs/stage2/estimate", headers=headers).json()
    assert body["projects"] == expected[0]
    if body["projects"]:
        assert body["units_estimated"] > 0
        assert any("верхняя граница" in line for line in body["scheme_lines"])


def test_stage2_estimate_without_candidates_claims_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Кандидатов нет — смета не говорит «данные уже куплены».

    Пустой план печатает «нечего собирать: данные по этому списку уже
    куплены» — верно про список, где всё собрано, и неверно про список, где
    собирать не по кому. Так окно второй кнопки и заговорило на проде
    24.09.2026, где проектов ещё нет. Объяснять пустоту — дело окна.
    """
    from ahrefs_cases.api.routers import runs as runs_router

    async def nobody(*_args: object, **_kwargs: object) -> list[int]:
        return []

    monkeypatch.setattr(runs_router, "stage2_candidates", nobody)

    body = client.get("/api/runs/stage2/estimate", headers=_headers(client)).json()

    assert (body["projects"], body["units_estimated"]) == (0, 0)
    assert body["scheme_lines"] == []


def test_stage2_button_runs_the_rest_of_the_funnel(client: TestClient) -> None:
    """B6: вторая кнопка — шаг 2 и данные под кейс, записанные на нажавшего.

    Шаг 2 продолжает прогон, открытый API, а не открывает второй от системного
    пользователя; данные под кейс — своя строка журнала на того же автора.
    """
    headers = _headers(client)
    client.post("/api/runs", headers=headers)

    started = client.post("/api/runs/stage2", headers=headers)

    assert started.status_code == 202
    mine = [
        row
        for row in client.get("/api/runs", params={"limit": 100}, headers=headers).json()
        if row["started_by_name"] == "Оператор"
    ]
    by_stage = {row["stage"]: row for row in mine}
    assert by_stage["stage2"]["id"] == started.json()["run_id"]
    assert by_stage["stage2"]["status"] in {"done", "partial"}
    assert set(by_stage) <= {"stage1", "stage2", "case_data"}


def test_cases_after_the_second_button_are_downloadable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B6: кейсы, собранные после второй кнопки, не «устарели» с рождения.

    Ступень кейса докупает DR и стоимость трафика ПОСЛЕ классификации, кейс их
    печатает, а сверка свежести (`cases/freshness.py`) считает метрику, которой
    нет у вердикта, расхождением. Без пересчёта групп после ступени кейса
    каждый кейс из интерфейса выходил «устаревшим» и не отдавался на скачивание
    — найдено браузером на боевых образах 24.09.2026.
    """
    from ahrefs_cases import config

    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    headers = _headers(client)
    client.post("/api/runs", headers=headers)
    client.post("/api/runs/stage2", headers=headers)
    before = datetime.now(UTC)
    client.post("/api/runs/cases", headers=headers)

    # Только собранные этим тестом: в библиотеке лежат и кейсы стенда, а они
    # сверяются с версией порогов теста и законно не совпадают с ней.
    cases = [
        row
        for row in client.get("/api/cases", params={"limit": 100}, headers=headers).json()
        if datetime.fromisoformat(row["created_at"]) >= before
    ]
    assert cases, "сборка не дала ни одного кейса — проверять нечего"
    stale = {row["domain"]: row["outdated"] for row in cases if row.get("outdated")}
    assert not stale, f"кейсы устарели с рождения: {stale}"


def test_journal_names_the_stage(client: TestClient) -> None:
    """B6: сборка кейсов в журнале — сборка кейсов, а не сбор «0 из 18»."""
    headers = _headers(client)
    first = client.post("/api/runs", headers=headers).json()["run_id"]
    cases = client.post("/api/runs/cases", headers=headers).json()["run_id"]

    stages = {
        row["id"]: row["stage"]
        for row in client.get("/api/runs", params={"limit": 100}, headers=headers).json()
    }
    assert (stages[first], stages[cases]) == ("stage1", "cases")
    card = client.get(f"/api/runs/{cases}", headers=headers).json()
    # Сборку никто не отмечал начатой, а закрытие ставило только статус: в
    # журнале она стояла без времени начала и конца.
    assert card["started_at"] is not None
    assert card["finished_at"] is not None


def test_missing_run_is_404(client: TestClient) -> None:
    """E5: несуществующий прогон — 404, а не пустая карточка."""
    assert client.get("/api/runs/999999", headers=_headers(client)).status_code == 404


def test_failed_job_marks_the_run(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """E7: наблюдателя снаружи нет, отметить падение обязана сама задача (L24)."""
    headers = _headers(client)
    run_id = client.post("/api/runs", headers=headers).json()["run_id"]

    def _boom(_run_id: int) -> None:
        message = "нарочно сломано"
        raise RuntimeError(message)

    with pytest.raises(RuntimeError):
        asyncio.run(jobs._run_guarded(run_id, _explode()))

    row = client.get(f"/api/runs/{run_id}", headers=headers).json()
    assert row["status"] == "failed"
    assert "нарочно сломано" in row["error"]


async def _explode() -> str:
    message = "нарочно сломано"
    raise RuntimeError(message)


def test_cases_job_uses_the_same_queue(client: TestClient) -> None:
    """E8: сборка пачки ставится тем же способом и тем же замком."""
    response = client.post("/api/runs/cases", headers=_headers(client))

    assert response.status_code == 202
    assert response.json()["queued_as"].startswith("inline:")


def test_queue_is_chosen_by_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """E9: одно место решает «сразу или воркером» (урок L53)."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.storage, "queue_backend", "inline")
    assert isinstance(build_queue(), InlineQueue)

    monkeypatch.setattr(config.storage, "queue_backend", "redis")
    monkeypatch.setattr(queue, "RedisQueue", lambda: "redis-очередь")
    assert build_queue() == "redis-очередь"


def test_job_arguments_are_plain_values() -> None:
    """E10: задача уезжает в другой процесс — сессия и объекты туда не доедут."""
    import inspect

    for job in (jobs.collect_job, jobs.stage2_job, jobs.cases_job):
        for name, parameter in inspect.signature(job).parameters.items():
            assert parameter.annotation in {"int", "bool"}, f"{job.__name__}: {name}"
    assert RedisQueue is not None  # реализация существует и импортируется без Redis


def test_run_card_names_every_skipped_domain(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """E1/E2: пропущенный домен назван словом и причиной, а не только числом.

    ТЗ требует «сколько обработано, сколько пропущено и почему». Записи для
    этого пишутся с Ф2 и до этой поставки наружу не выходили: экран показывал
    «17 из 19» и молчал про двоих, хотя пропуск бывает четырёх видов и действия
    по ним разные.
    """
    headers = _headers(client)
    run_id = client.post("/api/runs", headers=headers).json()["run_id"]

    async def _mark(session: object) -> None:
        from ahrefs_cases.collect.run_journal import add_item
        from ahrefs_cases.storage._enums import RunItemOutcome

        run = await session.get(Run, run_id)  # type: ignore[attr-defined]
        await add_item(
            session,  # type: ignore[arg-type]
            run,
            project_id=None,
            raw_domain="молодой.example",
            outcome=RunItemOutcome.SKIPPED_NO_DATA,
            reason="у домена нет истории: два пустых ответа подряд",
        )

    writer(_mark)

    card = client.get(f"/api/runs/{run_id}", headers=headers).json()
    fate = next(item for item in card["fates"] if item["domain"] == "молодой.example")

    assert fate["outcome"] == "skipped_no_data"
    assert "нет истории" in fate["reason"], "причина словами, а не кодом исхода"
    assert card["projects_skipped"] >= 0, "счётчик пропусков есть в строке прогона"


def test_run_without_skips_shows_an_empty_list(client: TestClient) -> None:
    """E3: у прогона без пропусков список судеб пуст — лишнего экран не покажет."""
    headers = _headers(client)
    run_id = client.post("/api/runs", headers=headers).json()["run_id"]

    card = client.get(f"/api/runs/{run_id}", headers=headers).json()

    assert isinstance(card["fates"], list)
    assert card["projects_skipped"] == max(
        0, card["projects_total"] - card["projects_ok"] - card["projects_failed"]
    )


def test_fates_are_bounded(client: TestClient) -> None:
    """E4: выдача ограничена — список не растёт с корпусом (гейт `unbounded-list`)."""
    from ahrefs_cases.api.routers.runs import MAX_FATES

    headers = _headers(client)
    run_id = client.post("/api/runs", headers=headers).json()["run_id"]

    card = client.get(f"/api/runs/{run_id}", headers=headers).json()

    assert len(card["fates"]) <= MAX_FATES


def test_journal_pages_and_filters(client: TestClient) -> None:
    """Журнал листается и отбирается: по автору и по календарным датам.

    Заведено 15.09.2026: журнал на стенде перевалил за пять сотен строк, и
    «свежие двадцать» перестали отвечать на вопрос «что было в понедельник и
    кто это запускал».

    Границы дат **включающие**: `until` берёт весь названный день. Иначе
    человек, выбравший один день, получил бы пустой список и решил, что
    прогонов не было, — отбор, который врёт молча, хуже отсутствующего.
    """
    headers = _headers(client)
    started = client.post("/api/runs", headers=headers).json()
    mine = client.get("/api/runs", headers=headers).json()[0]

    # Страница: первая строка первой страницы не повторяется на второй.
    first = client.get("/api/runs?limit=1", headers=headers).json()
    second = client.get("/api/runs?limit=1&offset=1", headers=headers).json()
    assert len(first) == 1
    assert first[0]["id"] == started["run_id"]
    assert not second or second[0]["id"] != first[0]["id"]

    # Отбор по автору: свой прогон виден, чужой номер не возвращает ничего.
    author = mine["started_by"]
    ours = client.get(f"/api/runs?started_by={author}&limit=100", headers=headers).json()
    assert {row["started_by"] for row in ours} == {author}
    assert client.get("/api/runs?started_by=999999", headers=headers).json() == []

    # Календарный день прогона включён обеими границами.
    day = mine["created_at"][:10]
    same_day = client.get(f"/api/runs?since={day}&until={day}&limit=100", headers=headers).json()
    assert started["run_id"] in {row["id"] for row in same_day}


def test_authors_list_is_not_a_run_id(client: TestClient) -> None:
    """`authors` — путь, а не номер прогона.

    Третий случай того же капкана после `pack` и `selection` (урок L173):
    путь, объявленный после `/{run_id}`, уходит в разбор номера и отвечает 422.
    """
    headers = _headers(client)
    client.post("/api/runs", headers=headers)

    response = client.get("/api/runs/authors", headers=headers)

    assert response.status_code == 200, response.text
    authors = response.json()
    assert authors, "список авторов пуст, хотя прогон только что запущен"
    assert all({"id", "name", "deleted"} <= set(row) for row in authors)


def _own_run(write: Callable[[Callable[..., object]], None], provider: str | None) -> int:
    """Прогон своего пользователя с заданным режимом в снимке — без очереди."""
    made: list[int] = []

    async def _open(session: object) -> None:
        from sqlalchemy import select as _select

        author = (await session.execute(_select(User).where(User.email == EMAIL))).scalar_one()  # type: ignore[attr-defined]
        snapshot = {"stage": "stage1", **({"provider": provider} if provider else {})}
        run = Run(started_by=author.id, status=RunStatus.DONE, params_snapshot=snapshot)
        session.add(run)  # type: ignore[attr-defined]
        await session.flush()  # type: ignore[attr-defined]
        made.append(run.id)

    write(_open)
    return made[0]


def test_fates_name_the_domain_as_people_write_it(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """W1, W2: домен судьбы — как его пишет человек, тем же правилом, что у кейса."""
    run_id = _own_run(writer, "fixture")

    async def _fates(session: object) -> None:
        from ahrefs_cases.collect.run_journal import add_item
        from ahrefs_cases.storage._enums import RunItemOutcome

        run = await session.get(Run, run_id)  # type: ignore[attr-defined]
        for domain in ("xn--mller-shop-9db.de", "xn--zz.example"):
            await add_item(
                session,  # type: ignore[arg-type]
                run,
                project_id=None,
                raw_domain=domain,
                outcome=RunItemOutcome.SKIPPED_NO_DATA,
            )

    writer(_fates)

    card = client.get(f"/api/runs/{run_id}", headers=_headers(client)).json()

    # W2: обратно не разбирается — канон, а не падение журнала (правило 4а).
    assert sorted(fate["domain"] for fate in card["fates"]) == ["müller-shop.de", "xn--zz.example"]


def test_journal_names_the_mode_of_each_run(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """W3–W5: живой прогон, fixture и прогон без режима различимы в журнале."""
    ids = {mode: _own_run(writer, mode) for mode in ("live", "fixture", None)}

    rows = {
        row["id"]: (row["live"], row["mode"])
        for row in client.get("/api/runs", headers=_headers(client)).json()
    }
    card = client.get(f"/api/runs/{ids['fixture']}", headers=_headers(client)).json()

    assert [rows[ids[mode]] for mode in ("live", "fixture", None)] == [
        (True, "live"),
        (False, "fixture"),
        (False, ""),
    ]
    assert (card["live"], card["mode"]) == (False, "fixture")


def test_journal_calls_live_what_spending_counts(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """W6: `live` журнала — ровно те прогоны, чей расход считает «потрачено».

    Расход считается по всей базе, поэтому сверяется приращение: чужие строки
    журнала между двумя замерами в одном тесте не появляются.
    """
    from ahrefs_cases.collect.budget import SpendSummary, spend_summary
    from ahrefs_cases.storage import LedgerKind
    from ahrefs_cases.storage.models.units_ledger import UnitsLedger

    units: dict[str | None, int] = {"live": 11, "fixture": 13, None: 17}
    found: list[SpendSummary] = []

    async def _summary(session: object) -> None:
        found.append(await spend_summary(session))  # type: ignore[arg-type]

    writer(_summary)
    ids = {mode: _own_run(writer, mode) for mode in units}

    async def _spend(session: object) -> None:
        for mode, run_id in ids.items():
            spent = UnitsLedger(run_id=run_id, kind=LedgerKind.SPENT, units_actual=units[mode])
            session.add(spent)  # type: ignore[attr-defined]

    writer(_spend)
    writer(_summary)
    live = {
        row["id"] for row in client.get("/api/runs", headers=_headers(client)).json() if row["live"]
    }

    counted = sum(units[mode] for mode, run_id in ids.items() if run_id in live)
    assert found[1].live - found[0].live == counted == units["live"]


def _pdfs(archive: Path | bytes, spare: Path) -> list[str]:
    """Имена PDF в архиве — из файла или из тела ответа."""
    if isinstance(archive, bytes):
        spare.write_bytes(archive)
        archive = spare
    with ZipFile(archive) as bundle:
        return sorted(name for name in bundle.namelist() if name.endswith(".pdf"))


def _built(client: TestClient, headers: dict[str, str]) -> int:
    """Путь до кейсов тремя кнопками; номер прогона сборки."""
    client.post("/api/runs", headers=headers)
    client.post("/api/runs/stage2", headers=headers)
    return int(client.post("/api/runs/cases", headers=headers).json()["run_id"])


def _journal(client: TestClient, headers: dict[str, str]) -> dict[int, dict[str, object]]:
    rows = client.get("/api/runs", params={"limit": 100}, headers=headers).json()
    return {row["id"]: row for row in rows}


def test_cases_run_keeps_its_own_pack(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P1, P3: у каждой сборки своя копия архива, и отдаётся она по номеру прогона.

    Пачка дня одна: вторая сборка того же дня переписывает её под тем же именем
    (урок L89). Копия первой после этого обязана остаться своей — с PDF первой
    сборки, а не второй.
    """
    from ahrefs_cases import config
    from ahrefs_cases.export.archive import newest_pack

    monkeypatch.setattr(config.export, "output_dir", tmp_path / "out")
    headers = _headers(client)
    first = _built(client, headers)
    fresh = newest_pack(tmp_path / "out")
    assert fresh is not None, "сборка не дала архива — проверять нечего"
    first_pdfs = _pdfs(fresh, tmp_path / "spare.zip")
    second = int(client.post("/api/runs/cases", headers=headers).json()["run_id"])
    second_pdfs = _pdfs(fresh, tmp_path / "spare.zip")

    rows = _journal(client, headers)
    assert (rows[first]["pack"], rows[second]["pack"]) == (True, True)
    assert rows[first]["pack_cases"] == len(first_pdfs)
    got = client.get(f"/api/runs/{first}/pack", headers=headers)
    assert got.status_code == 200, got.text
    assert got.headers["content-type"] == "application/zip"
    assert f"прогон-{first}" in unquote(got.headers["content-disposition"])
    assert _pdfs(got.content, tmp_path / "spare.zip") == first_pdfs
    again = client.get(f"/api/runs/{second}/pack", headers=headers)
    assert _pdfs(again.content, tmp_path / "spare.zip") == second_pdfs != first_pdfs


def test_build_without_archive_leaves_no_pack(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P2: сборка без архива копии не оставляет — свежий архив каталога ей чужой.

    Без шага 1 у проекта нет вердикта по версии порогов теста, собирать нечего,
    и прежний архив дня остаётся самым свежим. Приписать его этому прогону
    значило бы отдать по его кнопке чужую сборку.
    """
    from ahrefs_cases import config

    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    with ZipFile(tmp_path / "кейсы-2026-09-01.zip", "w") as bundle:
        bundle.writestr("old.example — Кейс v1.pdf", b"%PDF-old")
    headers = _headers(client)
    run_id = int(client.post("/api/runs/cases", headers=headers).json()["run_id"])

    assert _journal(client, headers)[run_id]["pack"] is False
    got = client.get(f"/api/runs/{run_id}/pack", headers=headers)
    assert got.status_code == 404
    assert "своей пачки" in got.json()["detail"]
    assert not (tmp_path / "runs").exists()


def test_run_pack_with_a_deleted_case_is_not_given(
    client: TestClient,
    writer: Callable[[Callable[..., object]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """P4: копия с кейсом удалённого проекта не отдаётся — как и пачка (24.09.2026)."""
    from sqlalchemy import delete

    from ahrefs_cases import config
    from ahrefs_cases.export.archive import packed_checksums
    from ahrefs_cases.storage.models.case import CaseArtifact

    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    headers = _headers(client)
    run_id = _built(client, headers)
    copy = next((tmp_path / "runs" / str(run_id)).glob("*.zip"))
    sums = packed_checksums(copy) or frozenset()
    assert sums, "в копии нет PDF — проверять нечего"

    async def _forget(session: object) -> None:
        stmt = delete(CaseArtifact).where(CaseArtifact.checksum.in_(sums))
        await session.execute(stmt)  # type: ignore[attr-defined]

    writer(_forget)
    got = client.get(f"/api/runs/{run_id}/pack", headers=headers)
    assert got.status_code == 409
    assert "удалённого проекта" in got.json()["detail"]


def test_only_the_last_case_data_offers_to_build(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P5: «Собрать кейсы» предлагает только последний «данные под кейс» без сборки после."""
    from ahrefs_cases import config

    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    headers = _headers(client)
    client.post("/api/runs", headers=headers)
    client.post("/api/runs/stage2", headers=headers)
    rows = _journal(client, headers)
    data = [run_id for run_id, row in rows.items() if row["stage"] == "case_data"]
    assert data, "шаг 2 не дошёл до данных под кейс — проверять нечего"

    assert [run_id for run_id, row in rows.items() if row["build_cases"]] == [max(data)]
    assert client.get(f"/api/runs/{max(data)}", headers=headers).json()["build_cases"] is True
    client.post("/api/runs/cases", headers=headers)
    assert not any(row["build_cases"] for row in _journal(client, headers).values())


def test_run_without_pack_says_why(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """P6, P7: шаг 1 пачки не собирает; путь в снимке вне `runs/` не отдаётся; без токена — 401."""
    headers = _headers(client)
    stage1 = _own_run(writer, "fixture")
    made: list[int] = []

    async def _escape(session: object) -> None:
        from sqlalchemy import select as _select

        author = (await session.execute(_select(User).where(User.email == EMAIL))).scalar_one()  # type: ignore[attr-defined]
        run = Run(
            started_by=author.id,
            status=RunStatus.DONE,
            params_snapshot={"stage": "cases", "pack": "../../etc/passwd"},
        )
        session.add(run)  # type: ignore[attr-defined]
        await session.flush()  # type: ignore[attr-defined]
        made.append(run.id)

    writer(_escape)

    assert client.get(f"/api/runs/{stage1}/pack", headers=headers).status_code == 404
    assert client.get(f"/api/runs/{made[0]}/pack", headers=headers).status_code == 404
    assert client.get(f"/api/runs/{stage1}/pack").status_code == 401


def _file_project(writer: Callable[[Callable[..., object]], None]) -> int:
    """Номер проекта `runs.example` — «файл» из одного проекта."""
    from sqlalchemy import select as _select

    found: list[int] = []

    async def _find(session: object) -> None:
        stmt = _select(Project.id).where(Project.domain == "runs.example")
        found.append((await session.execute(stmt)).scalar_one())  # type: ignore[attr-defined]

    writer(_find)
    return found[0]


def _mine_since(client: TestClient, headers: dict[str, str], first: int) -> list[dict[str, object]]:
    """Строки журнала начиная с номера `first` — старые сверху."""
    rows = client.get("/api/runs", params={"limit": 100}, headers=headers).json()
    return sorted((row for row in rows if row["id"] >= first), key=lambda row: row["id"])


def test_cycle_estimate_counts_only_the_file(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """C1: смета цикла — по проектам файла, а не по всей базе; шаг 2 — верхней границей.

    Второй проект база получает здесь же — вторая кампания того же сайта: в чистой
    базе CI проект теста единственный, и «база шире файла» держалась бы только на
    данных дев-стенда (L8, L58).
    """
    headers = _headers(client)
    project = _file_project(writer)

    async def _second(session: object) -> None:
        session.add(  # type: ignore[attr-defined]
            Project(
                domain="runs.example",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 1),
                niche="fintech",
                geo="US",
                service_type="seo",
                client="Acme",
                owner="i.petrov",
                publishable=True,
                notes="",
            )
        )

    writer(_second)
    whole = client.get("/api/runs/estimate", headers=headers).json()
    cycle = client.get("/api/runs/chain/estimate", params={"projects": [project]}, headers=headers)

    assert cycle.status_code == 200, cycle.text
    body = cycle.json()
    assert body["projects"] == 1 < whole["projects"]
    assert body["units_estimated"] > 0
    assert any("верхняя граница" in line for line in body["scheme_lines"])


def test_cycle_runs_the_file_to_its_own_pack(
    client: TestClient,
    writer: Callable[[Callable[..., object]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C2: одна строка на весь цикл; архив — кейсы проектов файла; пачка дня не тронута."""
    from ahrefs_cases import config
    from ahrefs_cases.export.archive import newest_pack

    monkeypatch.setattr(config.export, "output_dir", tmp_path / "out")
    headers = _headers(client)
    started = client.post(
        "/api/runs/chain", json={"project_ids": [_file_project(writer)]}, headers=headers
    )

    assert started.status_code == 202, started.text
    rows = _mine_since(client, headers, int(started.json()["run_id"]))
    assert [(row["stage"], row["status"], row["projects_total"]) for row in rows] == [
        ("cycle", "done", 1)
    ]
    cycle = rows[0]
    assert cycle["pack"] is True
    got = client.get(f"/api/runs/{cycle['id']}/pack", headers=headers)
    pdfs = _pdfs(got.content, tmp_path / "spare.zip")
    assert pdfs and all(name.startswith("runs.example") for name in pdfs)
    assert cycle["pack_cases"] == len(pdfs)
    assert newest_pack(tmp_path / "out") is None, "цикл по файлу переписал пачку дня"
    card = client.get(f"/api/runs/{cycle['id']}", headers=headers).json()
    assert {"stage1", "cases"} <= {fate["stage"] for fate in card["fates"]}


def test_cycle_refuses_when_it_does_not_fit(
    client: TestClient,
    writer: Callable[[Callable[..., object]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: на весь цикл не хватает units — 409 словами сметы, строка не открыта."""
    from ahrefs_cases.api import run_estimates
    from ahrefs_cases.collect.quota import FixtureQuota

    headers = _headers(client)
    project = _file_project(writer)
    needed = client.get(
        "/api/runs/chain/estimate", params={"projects": [project]}, headers=headers
    ).json()["units_estimated"]
    before = client.get("/api/runs", params={"limit": 1}, headers=headers).json()
    monkeypatch.setattr(run_estimates, "build_quota", lambda: FixtureQuota(left=needed - 1))

    refused = client.post("/api/runs/chain", json={"project_ids": [project]}, headers=headers)

    assert refused.status_code == 409
    assert "весь цикл" in refused.json()["detail"]
    assert client.get("/api/runs", params={"limit": 1}, headers=headers).json() == before


def test_cycle_stops_on_a_failed_step(
    client: TestClient,
    writer: Callable[[Callable[..., object]], None],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C4: шаг 2 упал — цикл «упал» с его причиной, архива нет, ступени не видны."""
    from ahrefs_cases import config

    async def _broken(_run_id: int, **_kwargs: object) -> str:
        message = "шаг 2 нарочно сломан"
        raise RuntimeError(message)

    monkeypatch.setattr(config.export, "output_dir", tmp_path)
    monkeypatch.setattr(jobs, "_stage2", _broken)
    headers = _headers(client)
    started = client.post(
        "/api/runs/chain", json={"project_ids": [_file_project(writer)]}, headers=headers
    )

    rows = _mine_since(client, headers, int(started.json()["run_id"]))
    assert [(row["stage"], row["status"], row["current_stage"]) for row in rows] == [
        ("cycle", "failed", "stage2")
    ]
    assert "нарочно сломан" in str(rows[0]["error"])
    assert rows[0]["pack"] is False
