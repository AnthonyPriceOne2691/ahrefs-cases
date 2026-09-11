"""Приём списка по HTTP и смета прогона до старта.

Примеры приёмки поставки `intake-api`: E1 (XLSX принят), E2 (битая строка),
E3 (повторная загрузка), E4 (неизвестный формат), E5 (предел размера),
E6 (закрытая Google Sheet), E7 (без права `run`), E8 (смета совпадает с планом),
E9 (не хватает квоты), E10 (остаток неизвестен), E11 (маршрут сметы),
E12 (окна точек у сметы и у задачи одни).

Записываем мимо приложения своим циклом и движком — уроки L51 и L54.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.run import Run
from ahrefs_cases.storage.models.user import User

PASSWORD = "очень-длинный-пароль"
EMAIL = "intake@test.local"
READER_EMAIL = "reader@test.local"
DOMAIN_PREFIX = "intake-api-"

HEADER = (
    "domain",
    "period_start",
    "period_end",
    "niche",
    "geo",
    "service_type",
    "work_volume",
    "client",
    "owner",
    "publishable",
)
GOOD_ROWS = 10


def _row(index: int, domain: str | None = None) -> list[str]:
    return [
        domain if domain is not None else f"{DOMAIN_PREFIX}{index}.example",
        "2025-01-01",
        "2025-12-01",
        "fintech",
        "US",
        "seo",
        "120",
        "Acme",
        "i.petrov",
        "yes",
    ]


def _xlsx(rows: list[list[str]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(list(HEADER))
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
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
        from sqlalchemy import delete

        from ahrefs_cases.storage.models.metric_point import MetricPoint
        from ahrefs_cases.storage.models.units_ledger import UnitsLedger

        for model in (UnitsLedger, MetricPoint):
            await session.execute(delete(model))  # type: ignore[attr-defined]
        await session.execute(delete(Run))  # type: ignore[attr-defined]
        await session.execute(  # type: ignore[attr-defined]
            delete(Project).where(Project.domain.like(f"{DOMAIN_PREFIX}%"))
        )
        await session.execute(  # type: ignore[attr-defined]
            delete(User).where(User.email.in_([EMAIL, READER_EMAIL]))
        )

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    monkeypatch.setattr(config.storage, "queue_backend", "inline")


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)

    async def _seed(session: object) -> None:
        session.add_all(  # type: ignore[attr-defined]
            [
                User(
                    email=EMAIL,
                    full_name="Оператор",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.USER,
                ),
                User(
                    email=READER_EMAIL,
                    full_name="Читатель",
                    password_hash=security.hash_password(PASSWORD),
                    group=UserGroup.USER,
                    permissions={"run": False},
                ),
            ]
        )

    writer(_seed)
    yield
    _cleanup(writer)


@pytest.fixture
def client(seeded: None) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _headers(client: TestClient, email: str = EMAIL) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


def _upload(client: TestClient, body: bytes, name: str = "список.xlsx") -> object:
    return client.post(
        "/api/intake/file",
        params={"filename": name},
        content=body,
        headers=_headers(client),
    )


def test_xlsx_upload_creates_projects(client: TestClient) -> None:
    """E1: книга на десять годных строк принята целиком."""
    response = _upload(client, _xlsx([_row(i) for i in range(GOOD_ROWS)]))

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] == GOOD_ROWS
    assert body["created"] == GOOD_ROWS
    assert body["rejected_rows"] == 0
    assert body["origin"] == "список.xlsx"


def test_broken_row_is_rejected_with_a_reason(client: TestClient) -> None:
    """E2: битая строка не останавливает загрузку и называет причину и номер."""
    rows = [_row(i) for i in range(GOOD_ROWS)]
    rows.append(_row(99, domain=""))

    body = _upload(client, _xlsx(rows)).json()

    assert body["accepted"] == GOOD_ROWS
    assert body["rejected_rows"] == 1
    rejection = body["rejections"][0]
    # +2: заголовок и нумерация с единицы — человек ищет строку глазами в Excel.
    assert rejection["row_no"] == GOOD_ROWS + 2
    assert rejection["field"] == "domain"
    assert rejection["reason"] == "missing_field"
    assert body["by_reason"]["missing_field"] == 1


def test_second_upload_updates_instead_of_doubling(client: TestClient) -> None:
    """E3: повторная загрузка того же файла законна и видна как «обновлено»."""
    book = _xlsx([_row(i) for i in range(GOOD_ROWS)])
    _upload(client, book)

    again = _upload(client, book).json()

    assert again["created"] == 0
    assert again["updated"] == GOOD_ROWS


def test_unknown_format_is_a_refusal_not_a_crash(client: TestClient) -> None:
    """E4: `.pdf` — отказ с объяснением, а не пятисотка от разбора."""
    response = _upload(client, b"%PDF-1.7 ...", name="отчёт.pdf")

    assert response.status_code == 400
    assert "не понимаю формат" in response.json()["detail"]


def test_body_over_the_limit_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E5: предел назван в отказе — человек должен знать, во что упёрся."""
    from ahrefs_cases.api.routers import intake

    monkeypatch.setattr(intake, "MAX_UPLOAD_BYTES", 1024)

    response = _upload(client, b"x" * 5000)

    assert response.status_code == 413
    assert "МБ" in response.json()["detail"]


def test_empty_body_is_refused(client: TestClient) -> None:
    """Пустое тело — отказ, а не «принято 0»: файла просто нет."""
    response = _upload(client, b"")

    assert response.status_code == 400
    assert "файла нет" in response.json()["detail"]


def _link(client: TestClient, url: str) -> object:
    return client.post("/api/intake/link", json={"url": url}, headers=_headers(client))


def test_closed_google_sheet_says_why(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """E6: закрытая таблица отвечает страницей входа со статусом 200 (L10).

    Донести это как `400` обязан роутер: «принято 0» отправило бы человека
    чинить свой файл вместо того, чтобы открыть доступ. Подменяется только
    загрузка байтов — разбор и различитель работают настоящие.
    """
    from ahrefs_cases.intake import gsheet_source

    monkeypatch.setattr(
        gsheet_source, "_http_fetch", lambda _url: b"<!doctype html><html>Sign in</html>"
    )

    response = _link(client, "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0")

    assert response.status_code == 400
    assert "недоступна по ссылке" in response.json()["detail"]


def test_unreachable_sheet_is_a_refusal_not_a_crash(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Сеть или 404 у Google — отказ с причиной: сломана ссылка, а не сервис."""
    import httpx

    from ahrefs_cases.intake import gsheet_source

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise httpx.ConnectError("сеть недоступна")

    # Подменяется сам запрос, а не наш загрузчик: проверяется именно то, что
    # загрузчик превращает беду транспорта в отказ с причиной.
    monkeypatch.setattr(gsheet_source.httpx, "get", _boom)

    response = _link(client, "https://docs.google.com/spreadsheets/d/abc123/edit")

    assert response.status_code == 400


def test_link_that_is_not_a_sheet_is_refused(client: TestClient) -> None:
    """Ссылка не на таблицу — отказ без единого запроса в сеть."""
    response = _link(client, "https://example.com/список.xlsx")

    assert response.status_code == 400
    assert "не похоже на ссылку Google Sheet" in response.json()["detail"]


def test_intake_requires_the_run_right(client: TestClient) -> None:
    """E7: приём тратит квоту следующим шагом — он закрыт правом `run`."""
    response = client.post(
        "/api/intake/file",
        params={"filename": "список.xlsx"},
        content=_xlsx([_row(0)]),
        headers=_headers(client, READER_EMAIL),
    )

    assert response.status_code == 403
    assert "run" in response.json()["detail"]


def test_intake_needs_a_token(client: TestClient) -> None:
    """Без токена список не принимается: это запись в базу сервиса."""
    assert (
        client.post("/api/intake/file", params={"filename": "x.xlsx"}, content=b"x").status_code
        == 401
    )


def _estimate(client: TestClient) -> dict[str, object]:
    response = client.get("/api/runs/estimate", headers=_headers(client))
    assert response.status_code == 200
    return response.json()


def test_estimate_matches_the_plan(client: TestClient) -> None:
    """E8 и E11: смета отвечает по своему адресу и совпадает с планом сбора.

    Совпадение проверяется не «похожестью чисел»: смета обязана быть тем же
    расчётом, который сделает прогон, иначе экран назовёт цену другого прогона.
    """
    _upload(client, _xlsx([_row(i) for i in range(GOOD_ROWS)]))

    body = _estimate(client)

    async def _plan_units() -> int:
        from ahrefs_cases.classify.windows import point_windows
        from ahrefs_cases.collect.factory import build_provider
        from ahrefs_cases.collect.plan import build_stage1_plan
        from ahrefs_cases.storage.session import get_sessionmaker

        async with get_sessionmaker()() as session:
            from sqlalchemy import select

            projects = list((await session.execute(select(Project))).scalars().all())
            plan = await build_stage1_plan(
                session,
                projects,
                source=build_provider().source,
                now=date.today(),
                windows=await point_windows(session),
            )
            return plan.estimated_units()

    assert body["projects"] == GOOD_ROWS
    assert body["units_estimated"] == asyncio.run(_plan_units())
    assert body["requests_planned"] > 0
    assert body["scheme_lines"]


def test_estimate_costs_nothing_and_opens_no_run(client: TestClient) -> None:
    """Смотреть цену бесплатно и не оставляет следа в журнале прогонов.

    Иначе человек, посмотревший смету и передумавший, держал бы резерв units и
    строку прогона, которой не было.
    """
    _upload(client, _xlsx([_row(i) for i in range(GOOD_ROWS)]))

    _estimate(client)

    assert client.get("/api/runs", headers=_headers(client)).json() == []


def test_estimate_refuses_when_quota_is_short(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E9: не хватает квоты — запуск закрыт, причина с числами."""
    from ahrefs_cases.api.routers import runs
    from ahrefs_cases.collect.quota import FixtureQuota

    _upload(client, _xlsx([_row(i) for i in range(GOOD_ROWS)]))
    monkeypatch.setattr(runs, "build_quota", lambda: FixtureQuota(left=1))

    body = _estimate(client)

    assert body["may_start"] is False
    assert body["verdict"] == "not_enough"
    assert "не хватает units" in str(body["reason"])
    assert body["quota_left"] == 1


def test_unknown_quota_is_not_the_same_as_empty(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E10: «остаток неизвестен» — свой вердикт (L23).

    «Квоты мало» лечится ожиданием, «остаток неизвестен» — починкой доступа к
    Ahrefs. Слить их значит показать человеку не ту причину.
    """
    from ahrefs_cases.api.routers import runs
    from ahrefs_cases.collect.ahrefs_transport import AhrefsUnavailableError

    class _Silent:
        async def units_left(self) -> int:
            raise AhrefsUnavailableError("Ahrefs не отвечает")

    _upload(client, _xlsx([_row(0)]))
    monkeypatch.setattr(runs, "build_quota", _Silent)

    body = _estimate(client)

    assert body["verdict"] == "unknown"
    assert body["may_start"] is False
    assert body["quota_left"] is None


def test_estimate_is_open_to_those_who_may_not_run(client: TestClient) -> None:
    """Смета — чтение: её видит и тот, кому запуск запрещён.

    Тот же приём, что у предпросмотра порогов: посмотреть, во что обойдётся
    прогон, полезно руководителю, который сам его не запускает.
    """
    response = client.get("/api/runs/estimate", headers=_headers(client, READER_EMAIL))

    assert response.status_code == 200


def test_queued_run_and_estimate_use_the_same_windows(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E12: прогон из очереди берёт окна точек оттуда же, откуда смета.

    Дефект, который чинит эта поставка: окна читал только CLI, а задача звала
    сбор без них — прогон, запущенный кнопкой, покупал не то же самое. Тест
    сравнивает **входы двух путей**, потому что по отдельности оба выглядели
    исправными.
    """
    from ahrefs_cases.collect import runner
    from ahrefs_cases.workers import jobs

    _upload(client, _xlsx([_row(0)]))
    seen: list[object] = []
    real = runner.collect_projects

    async def _spy(*args: object, **kwargs: object) -> object:
        seen.append(kwargs.get("windows"))
        return await real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(jobs, "collect_projects", _spy)
    client.post("/api/runs", headers=_headers(client))

    async def _expected() -> object:
        from ahrefs_cases.classify.windows import point_windows
        from ahrefs_cases.storage.session import get_sessionmaker

        async with get_sessionmaker()() as session:
            return await point_windows(session)

    assert seen, "задача не позвала сбор — проверять нечего"
    assert seen[0] is not None
    assert seen[0] == asyncio.run(_expected())
