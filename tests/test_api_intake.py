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
from tests.owned_rows import delete_owned, isolated_ruleset

from ahrefs_cases import config
from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import UserGroup
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.user import User

PASSWORD = "очень-длинный-пароль"
EMAIL = "intake@test.local"
READER_EMAIL = "reader@test.local"
RULESET = "тест-приём-api"
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


def _text_volume_row(index: int) -> list[str]:
    """Строка, заполненная по-человечески: объём работ словами, а не числом."""
    row = _row(index)
    row[6] = f"за 18 месяцев {index + 100} ссылок"
    return row


def _xlsx(rows: list[list[str]]) -> bytes:
    return _book([("Лист1", [list(HEADER), *rows])])


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
        from sqlalchemy import select

        # Домены приёма создаются с префиксом, поэтому список собирается
        # запросом, а не перечислением: их число меняется от теста к тесту.
        mine = (
            (
                await session.execute(
                    select(Project.domain).where(Project.domain.like(f"{DOMAIN_PREFIX}%"))
                )
            )  # type: ignore[attr-defined]
            .scalars()
            .all()
        )
        await delete_owned(session, domains=list(mine), emails=(EMAIL, READER_EMAIL))  # type: ignore[arg-type]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")
    monkeypatch.setattr(config.storage, "queue_backend", "inline")


@pytest.fixture
def seeded(migrated_db: None, writer: Callable[[Callable[..., object]], None]) -> Iterator[None]:
    _cleanup(writer)
    # Здесь тоже запускается прогон, а он классифицирует все проекты базы по
    # действующей версии порогов — значит, по своей, а не по стендовой (Z12).
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
    undo()
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
    """E2, V12: битая строка не останавливает загрузку и называет причину и номер."""
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


def test_text_volume_is_a_notice_not_a_refusal(client: TestClient) -> None:
    """E4 и E8: десять строк с текстовым объёмом принимаются, а ячейки видны.

    Ровно тот файл, который отклонялся целиком до этой поставки: объём работ
    написан словами, всё остальное в порядке.
    """
    body = _upload(client, _xlsx([_text_volume_row(i) for i in range(GOOD_ROWS)])).json()

    assert body["accepted"] == GOOD_ROWS
    assert body["rejected_rows"] == 0
    assert len(body["notices"]) == GOOD_ROWS
    assert body["notices"][0]["field"] == "work_volume"
    assert "ссылок" in body["notices"][0]["detail"]
    # Замечания не подмешиваются к отказам: иначе число отклонённых строк врёт.
    assert body["rejections"] == []


def test_second_upload_updates_instead_of_doubling(client: TestClient) -> None:
    """E3: повторная загрузка того же файла законна и видна как «обновлено»."""
    book = _xlsx([_row(i) for i in range(GOOD_ROWS)])

    first = _upload(client, book).json()
    again = _upload(client, book).json()

    assert again["created"] == 0
    assert again["updated"] == GOOD_ROWS
    # F1: те же проекты — те же номера; по ним экран считает смету цикла по файлу.
    assert len(first["project_ids"]) == GOOD_ROWS
    assert again["project_ids"] == first["project_ids"]


def test_unknown_format_is_a_refusal_not_a_crash(client: TestClient) -> None:
    """E4, V11: `.pdf` — отказ с объяснением, а не пятисотка от разбора."""
    response = _upload(client, b"%PDF-1.7 ...", name="отчёт.pdf")

    assert response.status_code == 400
    assert "не понимаю формат" in response.json()["detail"]


def test_body_over_the_limit_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E5, V11: предел назван в отказе — человек должен знать, во что упёрся."""
    from ahrefs_cases.api.routers import intake

    monkeypatch.setattr(intake, "MAX_UPLOAD_BYTES", 1024)

    response = _upload(client, b"x" * 5000)

    assert response.status_code == 413
    assert "МБ" in response.json()["detail"]


def test_empty_body_is_refused(client: TestClient) -> None:
    """V6: пустой файл — отказ, а не «принято 0», и словами человека.

    «Пустое тело запроса» — язык протокола: файл человек выбрал, и слышать, что
    «файла нет», ему странно. Пуст сам файл, так и сказано.
    """
    response = _upload(client, b"")

    assert response.status_code == 400
    assert "файл пуст" in response.json()["detail"]
    assert "тело запроса" not in response.json()["detail"]


def _link(client: TestClient, url: str) -> object:
    return client.post("/api/intake/link", json={"url": url}, headers=_headers(client))


def test_closed_google_sheet_says_why(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """E6, V15: закрытая таблица отвечает страницей входа со статусом 200 (L10).

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
    # Своя причина: «откройте доступ», а не «поправьте колонки» (V15).
    assert "не подходит" not in response.json()["detail"]


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


# --- Брак файла: отказ целиком, база не тронута (поставка file-import-explains-and-refuses)
#
# До неё файл без нужных колонок отвечал `200`, и экран писал «Принято из …»
# над таблицей «в файле нет колонки» — ошибка файла выглядела успешным приёмом.
# Нечитаемая книга и длинная двоичная строка ответа не получали вовсе: `500`.

RUSSIAN_HEADER = ["домен", "начало", "конец", "ниша", "гео", "услуга", "клиент"]


def _csv(
    header: list[str], rows: list[list[str]], sep: str = ",", encoding: str = "utf-8"
) -> bytes:
    lines = [sep.join(header), *(sep.join(row) for row in rows)]
    return ("\n".join(lines) + "\n").encode(encoding)


def _book(sheets: list[tuple[str, list[list[str]]]]) -> bytes:
    """Книга из нескольких листов: список бывает не на первом."""
    workbook = Workbook()
    for index, (title, matrix) in enumerate(sheets):
        sheet = workbook.active if index == 0 else workbook.create_sheet()
        assert sheet is not None
        sheet.title = title
        for values in matrix:
            sheet.append(values)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _without(*dropped: str) -> tuple[list[str], list[list[str]]]:
    """Шапка и строки без названных колонок — как будто их в файле не было."""
    keep = [index for index, name in enumerate(HEADER) if name not in dropped]
    rows = [[_row(i)[index] for index in keep] for i in range(3)]
    return [HEADER[index] for index in keep], rows


def _own_projects(write: Callable[[Callable[..., object]], None]) -> int:
    """Проекты этого модуля (по префиксу): база общая, чужие не считаются (L68)."""
    found: list[int] = []

    async def _count(session: object) -> None:
        from sqlalchemy import func, select

        query = select(func.count()).select_from(Project)
        query = query.where(Project.domain.like(f"{DOMAIN_PREFIX}%"))
        found.append((await session.execute(query)).scalar_one())  # type: ignore[attr-defined]

    write(_count)
    return found[0]


def _refusal(response: object) -> str:
    assert response.status_code == 400, response.text  # type: ignore[attr-defined]
    detail = response.json()["detail"]  # type: ignore[attr-defined]
    assert isinstance(detail, str)
    return detail


def test_unfit_file_is_refused_and_nothing_is_written(
    client: TestClient, writer: Callable[[Callable[..., object]], None]
) -> None:
    """V1: нет двух колонок — отказ с их именами и перечнем ожидаемых, в базе пусто.

    Строки файла при этом годные: без проверки файла целиком приём записал бы
    три проекта без периода и гео — и отчитался бы, что всё в порядке.
    """
    header, rows = _without("period_start", "geo")
    book = _book([("Лист1", [header, *rows])])

    detail = _refusal(_upload(client, book))

    assert detail.startswith("Файл «список.xlsx» не подходит: нет колонок period_start, geo.")
    assert ", ".join(HEADER) in detail
    assert _own_projects(writer) == 0


@pytest.mark.parametrize(
    ("separator", "encoding"),
    [(",", "utf-8"), (";", "cp1251")],
)
def test_russian_header_is_refused_with_what_was_read(
    client: TestClient, separator: str, encoding: str
) -> None:
    """V2: шапка по-русски — отказ показывает прочитанное и ожидаемое латиницей.

    Кодировка и разделитель при этом разобраны верно: «домен» прочитан словом,
    а не кракозябрами — значит, дело в именах, и текст обязан сказать именно это.
    """
    body = _csv(RUSSIAN_HEADER, [_row(0)], sep=separator, encoding=encoding)

    detail = _refusal(_upload(client, body, name="список.csv"))

    assert "нет ни одной нужной колонки" in detail
    assert "В первой строке сейчас: «домен», «начало»" in detail
    assert ", ".join(HEADER) in detail


def test_foreign_delimiter_shows_the_unsplit_header(client: TestClient) -> None:
    """V3: разделитель `|` — шапка не разделилась, и отказ показывает её одной ячейкой."""
    detail = _refusal(_upload(client, _csv(list(HEADER), [_row(0)], sep="|"), name="список.csv"))

    assert "В первой строке сейчас: «domain|period_start|" in detail
    assert "Шапка не разделилась на колонки" in detail


def test_near_names_are_suggested_not_accepted(client: TestClient) -> None:
    """V4: `Period Start` не принимается за `period_start` — отказ называет ближайшее имя.

    Регистр приём прощает (`Domain` — это `domain`), поэтому человек ждёт, что
    простит и пробел. Не прощает — и обязан сказать, какое имя поправить.
    """
    spaced = [name.replace("_", " ").title() for name in HEADER]

    detail = _refusal(_upload(client, _csv(spaced, [_row(0)]), name="список.csv"))

    for name in ("period_start", "period_end", "service_type", "work_volume"):
        assert f"{name} — в шапке «{name.replace('_', ' ')}», переименуйте" in detail


@pytest.mark.parametrize("tail", [[], [[""] * len(HEADER), [""] * len(HEADER)]])
def test_header_only_is_refused(client: TestClient, tail: list[list[str]]) -> None:
    """V5: одна шапка (и пустые строки, которые Excel дописывает хвостом) — отказ."""
    detail = _refusal(_upload(client, _csv(list(HEADER), tail), name="список.csv"))

    assert "только шапка — строк со списком нет" in detail


@pytest.mark.parametrize(
    "first",
    [("Пусто", []), ("Инструкция", [["Заполните лист «Список»"]])],
)
def test_list_on_another_sheet_is_named(
    client: TestClient, first: tuple[str, list[list[str]]]
) -> None:
    """V7: читается первый лист — отказ называет его и лист, где список лежит."""
    book = _book([first, ("Список", [list(HEADER), _row(0)])])

    detail = _refusal(_upload(client, book, name="книга.xlsx"))

    assert f"Читается первый лист книги — «{first[0]}»" in detail
    assert "«Список»" in detail


def _zip_without_book() -> bytes:
    import zipfile

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<document/>")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n", id="pdf"),
        pytest.param(_csv(list(HEADER), [_row(0)]), id="csv"),
        pytest.param(_zip_without_book(), id="docx"),
        pytest.param(_xlsx([_row(0)])[:2000], id="truncated"),
    ],
)
def test_unreadable_book_is_refused_not_crashed(client: TestClient, body: bytes) -> None:
    """V8: не книга под именем `.xlsx` — отказ, а не пятисотка от openpyxl."""
    detail = _refusal(_upload(client, body, name="список.xlsx"))

    assert "не читается как книга Excel" in detail


@pytest.mark.parametrize(
    ("body", "said"),
    [
        pytest.param(_xlsx([_row(0)]), "не похож на текст", id="book"),
        pytest.param(b"%PDF-1.7\n" + bytes(range(256)) * 8, "не похож на текст", id="pdf"),
        pytest.param(b"x" * 200_000, "не читается как CSV", id="long-line"),
    ],
)
def test_binary_csv_is_refused(client: TestClient, body: bytes, said: str) -> None:
    """V9: книга или PDF под именем `.csv` — отказ, а не «Принято» с мусором в шапке.

    Строка длиннее предела модуля `csv` (131 072 символа) роняла разбор
    `csv.Error`, и человек получал пятисотку.
    """
    detail = _refusal(_upload(client, body, name="список.csv"))

    assert said in detail


def test_doubled_column_is_refused(client: TestClient) -> None:
    """V10: две колонки `domain` — непонятно, какую читать; раньше молча бралась последняя.

    Беды шапки названы разом: нехватка колонки и дубль в одном отказе, а не в
    двух загрузках подряд.
    """
    header = [*(name for name in HEADER if name != "geo"), "domain"]
    row = [value for name, value in zip(HEADER, _row(0), strict=True) if name != "geo"]
    body = _csv(header, [[*row, f"{DOMAIN_PREFIX}other.example"]])

    detail = _refusal(_upload(client, body, name="список.csv"))

    assert "нет колонки geo." in detail
    assert "В шапке дважды: domain" in detail


def _sheet_answers(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    """Подменить только загрузку байтов: разбор и проверка работают настоящие."""
    from ahrefs_cases.intake import gsheet_source

    monkeypatch.setattr(gsheet_source, "_http_fetch", lambda _url: body)


SHEET = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=7"


def test_sheet_without_columns_is_refused(
    client: TestClient,
    writer: Callable[[Callable[..., object]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """V13: таблица по ссылке без двух колонок — тот же отказ, что у файла."""
    header, rows = _without("client", "owner")
    _sheet_answers(monkeypatch, _csv(header, rows))

    detail = _refusal(_link(client, SHEET))

    assert detail.startswith("Таблица по ссылке не подходит: нет колонок client, owner.")
    assert ", ".join(HEADER) in detail
    assert _own_projects(writer) == 0


@pytest.mark.parametrize(
    ("body", "said", "names_the_sheet"),
    [
        pytest.param(b"", "нет ни одной строки", True, id="empty-sheet"),
        pytest.param(_csv(list(HEADER), []), "только шапка", False, id="header-only"),
        pytest.param(_csv(RUSSIAN_HEADER, [_row(0)]), "нет ни одной нужной", True, id="russian"),
    ],
)
def test_unfit_sheet_is_refused_like_a_file(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    said: str,
    names_the_sheet: bool,
) -> None:
    """V14: пустой лист, одна шапка, шапка по-русски — отказ, а не «Принято».

    Лист таблицы выбирается `gid` в ссылке, и когда на нём нет ничего своего,
    отказ говорит, какой лист прочитан: список мог лежать на соседнем.
    """
    _sheet_answers(monkeypatch, body)

    detail = _refusal(_link(client, SHEET))

    assert said in detail
    assert ("gid=7" in detail) is names_the_sheet


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

    # Смета считается по **всей** базе, а не по последней загрузке: у дев-базы
    # своя история, и требовать «ровно десять проектов» значит проверять
    # содержимое машины, а не свойство сметы (тот же класс, что L58 и L68).
    assert body["projects"] >= GOOD_ROWS
    assert body["units_estimated"] == asyncio.run(_plan_units())
    assert body["requests_planned"] > 0
    assert body["scheme_lines"]


def test_estimate_costs_nothing_and_opens_no_run(client: TestClient) -> None:
    """Смотреть цену бесплатно и не оставляет следа в журнале прогонов.

    Иначе человек, посмотревший смету и передумавший, держал бы резерв units и
    строку прогона, которой не было.
    """
    _upload(client, _xlsx([_row(i) for i in range(GOOD_ROWS)]))
    # Считаем прогоны до и после, а не требуем пустого журнала: в дев-базе
    # живут чужие прогоны, и «журнал пуст» проверяло бы содержимое машины, а
    # не свойство сметы (уроки L68, L79).
    before = len(client.get("/api/runs", headers=_headers(client)).json())

    _estimate(client)

    assert len(client.get("/api/runs", headers=_headers(client)).json()) == before


def test_estimate_refuses_when_quota_is_short(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E9: не хватает квоты — запуск закрыт, причина с числами."""
    from ahrefs_cases.api import run_estimates
    from ahrefs_cases.collect.quota import FixtureQuota

    _upload(client, _xlsx([_row(i) for i in range(GOOD_ROWS)]))
    monkeypatch.setattr(run_estimates, "build_quota", lambda: FixtureQuota(left=1))

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
    from ahrefs_cases.api import run_estimates
    from ahrefs_cases.collect.ahrefs_transport import AhrefsUnavailableError

    class _Silent:
        async def units_left(self) -> int:
            raise AhrefsUnavailableError("Ahrefs не отвечает")

    _upload(client, _xlsx([_row(0)]))
    monkeypatch.setattr(run_estimates, "build_quota", _Silent)

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


def test_quota_source_follows_the_key_not_the_series_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Остаток спрашивается у ключа, а не у режима рядов.

    До 15.09.2026 источник остатка привязывался к `provider`, и на стенде с
    фикстурными рядами смета показывала «Остаток квоты: 10 000» — зашитое
    учебное число, выданное за настоящий остаток ключа (около 1,46 млн). По
    этой строке человек решает, запускать ли прогон.

    Признак — ключ, и это не придирка к формулировке: запрос остатка бесплатен
    (`subscription-info`, 0 units), а **без ключа ходить в сеть нельзя вовсе**.
    Поэтому проверяются оба конца: с ключом живой источник, без ключа —
    учебный, и мягкий стоп продолжает срабатывать в разработке.
    """
    from ahrefs_cases.collect.factory import build_quota
    from ahrefs_cases.collect.quota import FixtureQuota, LiveQuota

    monkeypatch.setattr(config.ahrefs, "api_key", "")
    monkeypatch.setattr(config.ahrefs, "provider", "fixture")
    assert isinstance(build_quota(), FixtureQuota)

    monkeypatch.setattr(config.ahrefs, "api_key", "ключ")
    # Режим рядов остаётся фикстурным — источник остатка от него не зависит.
    assert isinstance(build_quota(), LiveQuota)
