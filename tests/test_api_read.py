"""Читающие роутеры: проекты, кейсы, расход.

Примеры приёмки поставки `api-read`: E1 (без токена), E2 (список с группами),
E3 (фильтры), E4 (граница выдачи), E5 (карточка), E6 (нет проекта), E7 (проект
без вердикта), E8 (библиотека), E9 (скачивание), E10 (расход).

Приложение поднимается с нашим `lifespan` — иначе соединение утечёт в чужой
тест (урок L51). Данные пишутся своим движком и чистятся до и после (L8).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.owned_rows import active_versions, delete_owned, make_active, restore_active

from ahrefs_cases.api import security
from ahrefs_cases.api.main import app
from ahrefs_cases.storage import Group, Metric, MetricSource, UserGroup
from ahrefs_cases.storage.models.case import Case, CaseArtifact
from ahrefs_cases.storage.models.metric_point import MetricPoint
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.user import User
from ahrefs_cases.storage.models.verdict import Verdict

PASSWORD = "очень-длинный-пароль"
EMAIL = "reader@test.local"
DOMAINS = ("alpha.example", "beta.example")


@pytest.fixture(scope="module")
def writer() -> Iterator[Callable[[Callable[..., object]], None]]:
    """Один цикл и один движок на модуль — для записи мимо приложения.

    Тесты API пишут данные своей сессией: приложение ходит в ту же базу, но в
    своём цикле. Прежний вариант поднимал движок на каждый вызов, и закрытые
    соединения всплывали `ResourceWarning`ом **в случайном** тесте — при
    `filterwarnings = ["error"]` это падение там, где ничего не ломали (L51).
    Один долгоживущий цикл делает закрытие детерминированным.
    """
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


def _remember_stand(write: Callable[[Callable[..., object]], None]) -> list[str]:
    """Что было активно на стенде до теста."""
    found: list[str] = []

    async def _read(session: object) -> None:
        found.extend(await active_versions(session))  # type: ignore[arg-type]

    write(_read)
    return found


def _restore_stand(write: Callable[[Callable[..., object]], None], versions: list[str]) -> None:
    """Вернуть стенду его действующую версию порогов."""

    async def _write(session: object) -> None:
        await restore_active(session, versions)  # type: ignore[arg-type]

    write(_write)


def _cleanup(write: Callable[[Callable[..., object]], None]) -> None:
    async def _delete(session: object) -> None:
        await delete_owned(session, domains=DOMAINS, emails=(EMAIL,))  # type: ignore[arg-type]

    write(_delete)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from ahrefs_cases import config

    monkeypatch.setattr(config.auth, "jwt_secret", "тестовый-секрет-подписи")


@pytest.fixture
def seeded(
    migrated_db: None,
    tmp_path: Path,
    writer: Callable[[Callable[..., object]], None],
) -> Iterator[dict[str, int]]:
    """Два проекта: у первого вердикт `good` и кейс, у второго вердикта нет."""
    was_active = _remember_stand(writer)
    _cleanup(writer)
    ids: dict[str, int] = {}
    artifact_path = tmp_path / "alpha.example — Кейс.pdf"
    artifact_path.write_bytes("%PDF-1.7 тест".encode())

    async def _seed(session: object) -> None:
        from ahrefs_cases.classify.rulesets import seed_thresholds

        # Берём засеянную версию, а не свою: выключать чужую активность значит
        # оставить дев-базу без активных порогов следующему модулю (урок L8).
        ruleset = await seed_thresholds(session)  # type: ignore[arg-type]
        # Версия теста должна быть **единственной** действующей: вердикт
        # карточки ищется по действующей, а на общем стенде активна может быть
        # чужая — тогда тест находит `verdict: null` и падает по причине
        # окружения, а не кода (найдено 13.09.2026). Прежняя активность
        # запомнена и возвращается в уборке.
        await make_active(session, ruleset.version)  # type: ignore[arg-type]
        user = User(
            email=EMAIL,
            full_name="Читатель",
            password_hash=security.hash_password(PASSWORD),
            group=UserGroup.USER,
        )
        projects = [
            Project(
                domain=domain,
                period_start=date(2025, 1, 1),
                period_end=date(2025, 12, 1),
                niche="fintech",
                geo="US",
                service_type="seo",
                client="Acme",
                owner="i.petrov",
                publishable=True,
                notes="",
            )
            for domain in DOMAINS
        ]
        session.add_all([user, *projects])  # type: ignore[attr-defined]
        await session.flush()  # type: ignore[attr-defined]

        verdict = Verdict(
            project_id=projects[0].id,
            ruleset_id=ruleset.id,
            group=Group.GOOD,
            score=1400.0,
            reasons={
                "checks": [
                    {
                        "subject": "org_traffic",
                        "fact": 140.0,
                        "threshold": 50.0,
                        "passed": True,
                        "decisive": True,
                        "note": "рост выше порога",
                    }
                ]
            },
            point_a={"values": {"org_traffic": 1000.0}, "derived": {"kw_top10": 10.0}},
            point_b={"values": {"org_traffic": 2400.0}, "derived": {"kw_top10": 25.0}},
            source=MetricSource.FIXTURE,
        )
        session.add_all(  # type: ignore[attr-defined]
            [
                verdict,
                MetricPoint(
                    project_id=projects[0].id,
                    metric=Metric.ORG_TRAFFIC,
                    point_date=date(2025, 1, 1),
                    value=1000.0,
                    source=MetricSource.FIXTURE,
                    fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            ]
        )
        await session.flush()  # type: ignore[attr-defined]

        case = Case(
            project_id=projects[0].id,
            verdict_id=verdict.id,
            version=1,
            anonymized=False,
            highlights={"picked": []},
            narrative="Текст кейса.",
        )
        session.add(case)  # type: ignore[attr-defined]
        await session.flush()  # type: ignore[attr-defined]
        session.add(  # type: ignore[attr-defined]
            CaseArtifact(
                case_id=case.id,
                fmt="PDF",
                path=str(artifact_path),
                filename=artifact_path.name,
                checksum="0" * 64,
                built_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        ids["project"] = projects[0].id
        ids["no_verdict"] = projects[1].id
        ids["case"] = case.id
        ids["verdict"] = verdict.id

    writer(_seed)
    yield ids
    _cleanup(writer)
    _restore_stand(writer, was_active)


@pytest.fixture
def client(seeded: dict[str, int]) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _token(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_projects_need_a_token(client: TestClient) -> None:
    """E1: читающий роутер закрыт тем же правом, что и всё остальное."""
    assert client.get("/api/projects").status_code == 401


def test_projects_list_shows_groups(client: TestClient) -> None:
    """E2 и E7: у классифицированного группа есть, у второго — `null`."""
    rows = client.get("/api/projects", headers=_token(client)).json()

    by_domain = {row["domain"]: row for row in rows}
    assert by_domain["alpha.example"]["group"] == "good"
    assert by_domain["beta.example"]["group"] is None


def test_filters_narrow_the_list(client: TestClient, seeded: dict[str, int]) -> None:
    """E3: фильтр по группе и поиск по домену.

    Проверяется **свойство фильтра**, а не содержимое базы: в дев-базе живут
    чужие проекты, в том числе «хорошие», и требовать «в ответе ровно мой»
    значило бы проверять машину (уроки L68, L79).
    """
    headers = _token(client)

    only_good = client.get("/api/projects", params={"group": "good"}, headers=headers).json()
    by_query = client.get("/api/projects", params={"query": "beta"}, headers=headers).json()

    domains = [row["domain"] for row in only_good]
    assert "alpha.example" in domains
    assert "beta.example" not in domains, "фильтр обязан отсеять проект другой группы"
    assert {row["group"] for row in only_good} == {"good"}
    assert [row["domain"] for row in by_query] == ["beta.example"]


def test_limit_above_the_ceiling_is_refused(client: TestClient) -> None:
    """E4: граница выдачи не обходится параметром."""
    response = client.get("/api/projects", params={"limit": 1000}, headers=_token(client))

    assert response.status_code == 422


def test_card_shows_verdict_points_and_series(client: TestClient, seeded: dict[str, int]) -> None:
    """E5: карточка отвечает тем же, по чему принято решение (урок L41)."""
    card = client.get(f"/api/projects/{seeded['project']}", headers=_token(client)).json()

    assert card["verdict"]["group"] == "good"
    assert card["verdict"]["reasons"][0]["subject"] == "org_traffic"
    assert card["verdict"]["point_b"]["org_traffic"] == 2400.0
    assert card["verdict"]["point_b"]["kw_top10"] == 25.0
    assert card["series"][0]["metric"] == "org_traffic"


def test_card_says_when_numbers_and_curves_come_from_different_data(
    client: TestClient, seeded: dict[str, int]
) -> None:
    """E7: карточка кладёт числа вердикта рядом с кривыми рядов — та же пара,
    что разъехалась в кейсе (Z10). Значит и предупреждать обязана она же.

    Решает сервер: правило одно на лист PDF и на экран. Сравнение двух строк на
    фронте было бы вторым экземпляром правила — и разошлось бы с первым на
    случае «источник не записан вовсе».
    """
    headers = _token(client)
    same = client.get(f"/api/projects/{seeded['project']}", headers=headers).json()

    assert same["verdict"]["source"] == "fixture"
    assert same["series_source"] == "fixture"
    assert same["source_mismatch"] is None

    other = client.get(f"/api/projects/{seeded['project']}?source=live", headers=headers).json()

    assert other["source_mismatch"] is not None
    assert "fixture" in other["source_mismatch"] and "live" in other["source_mismatch"]


def test_card_compares_points_with_labels(client: TestClient, seeded: dict[str, int]) -> None:
    """E2 и E10 (`web-project-card`): сравнение А → Б приходит готовыми строками.

    Подпись и рост считает сервер: словарь подписей и арифметика роста живут в
    кейсе и классификации, и вторая копия на фронте разошлась бы с первой —
    экран и PDF начали бы называть метрики по-разному (урок L75).
    """
    card = client.get(f"/api/projects/{seeded['project']}", headers=_token(client)).json()

    rows = {row["subject"]: row for row in card["verdict"]["comparison"]}
    traffic = rows["org_traffic"]

    assert traffic["label"] == "органический трафик"
    assert traffic["before"] == 1000.0
    assert traffic["after"] == 2400.0
    assert traffic["absolute"] == 1400.0
    assert traffic["pct"] == pytest.approx(140.0)
    # Производная «топ-10» сравнивается наравне с покупными метриками.
    assert rows["kw_top10"]["label"] == "ключи в топ-10"


def test_comparison_skips_half_measured_metrics(client: TestClient, seeded: dict[str, int]) -> None:
    """Метрика, купленная только к одной точке, в сравнение не попадает.

    Показать половину строки значило бы предложить сравнить число с пустотой.
    """
    card = client.get(f"/api/projects/{seeded['project']}", headers=_token(client)).json()

    subjects = {row["subject"] for row in card["verdict"]["comparison"]}
    assert "refdomains" not in subjects


def test_missing_project_is_404(client: TestClient) -> None:
    """E6: пустая карточка выглядела бы как «проект без данных»."""
    assert client.get("/api/projects/999999", headers=_token(client)).status_code == 404


def test_case_library_and_download(client: TestClient, seeded: dict[str, int]) -> None:
    """E8 и E9: библиотека и файл под тем же именем, что уйдёт клиенту."""
    headers = _token(client)
    rows = client.get("/api/cases", headers=headers).json()
    assert rows[0]["domain"] == "alpha.example"
    assert rows[0]["filename"].endswith("Кейс.pdf")

    downloaded = client.get(f"/api/cases/{seeded['case']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-")


def test_library_shows_one_case_per_project(
    client: TestClient,
    seeded: dict[str, int],
    writer: Callable[[Callable[..., object]], None],
) -> None:
    """Библиотека отвечает «что отправить», а не «что когда собиралось».

    Пересборка добавляет версию, не затирая прежнюю: за несколько сборок один
    проект занимает десяток строк, и на сотне доменов первая страница достаётся
    двум-трём из них. Найдено прогоном живого экрана — шесть проектов дали
    пятьдесят строк.
    """

    async def _second_version(session: object) -> None:
        verdict_id = seeded["verdict"]
        session.add(  # type: ignore[attr-defined]
            Case(
                project_id=seeded["project"],
                verdict_id=verdict_id,
                version=2,
                anonymized=False,
                highlights={"picked": []},
                narrative="Текст кейса версии 2.",
            )
        )

    writer(_second_version)
    headers = _token(client)

    # Смотрим только свои строки: дев-база общая, и в ней живут кейсы,
    # собранные руками (урок L79).
    def ours(rows: list[dict[str, object]]) -> list[int]:
        return sorted(int(row["version"]) for row in rows if row["domain"] == DOMAINS[0])

    default = client.get("/api/cases?limit=100", headers=headers).json()
    assert ours(default) == [2]

    history = client.get("/api/cases?limit=100&all_versions=true", headers=headers).json()
    assert ours(history) == [1, 2]


def test_library_narrows_to_one_project(client: TestClient, seeded: dict[str, int]) -> None:
    """Карточка проекта спрашивает свой кейс, а не листает чужую библиотеку.

    Без фильтра единственный способ узнать номер кейса — выкачать библиотеку и
    найти строку перебором: на сотне доменов первая страница занята чужими
    проектами, и «моего кейса нет» становится неотличимо от «он на второй
    странице». Фильтр отвечает на тот же вопрос («какой файл отправить
    клиенту»), поэтому живёт тем же путём, а не вторым.
    """
    headers = _token(client)
    mine = client.get(f"/api/cases?project_id={seeded['project']}", headers=headers).json()

    assert mine, "кейс засеянного проекта не нашёлся по фильтру"
    assert {int(row["project_id"]) for row in mine} == {seeded["project"]}
    assert int(mine[0]["id"]) == seeded["case"]

    # Чужого проекта с таким номером быть не может: фильтр обязан отвечать
    # пустым списком, а не «первой попавшейся» строкой библиотеки.
    alien = client.get("/api/cases?project_id=999999", headers=headers).json()
    assert alien == []


def test_selection_returns_one_archive(client: TestClient, seeded: dict[str, int]) -> None:
    """Выбранные кейсы приезжают одним архивом, а не пачкой загрузок.

    Пачкой нельзя: браузер разрешает вкладке одну загрузку за жест человека и
    остальные обрывает молча — из десяти выбранных дошли бы два, и о восьми
    никто бы не узнал.
    """
    headers = _token(client)
    response = client.get(f"/api/cases/selection/download?ids={seeded['case']}", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content.startswith(b"PK")


def test_selection_names_the_cases_it_could_not_give(
    client: TestClient, seeded: dict[str, int]
) -> None:
    """Отказ называет НОМЕРА, а не «что-то не нашлось».

    Выборка человека — это список, и «один из них недоступен» без имени
    заставляет перебирать заново весь список руками.
    """
    headers = _token(client)
    response = client.get(
        f"/api/cases/selection/download?ids={seeded['case']}&ids=999999", headers=headers
    )

    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_selection_word_does_not_become_a_case_id(client: TestClient) -> None:
    """`selection` — маршрут, а не номер кейса.

    Тот же капкан, в который уже попадало слово `pack`: при объявлении после
    `/{case_id}/download` путь уходит в разбор номера и отвечает 422 вместо
    работы.
    """
    response = client.get("/api/cases/selection/download?ids=1", headers=_token(client))
    assert response.status_code != 422


def test_download_without_file_is_404(
    client: TestClient,
    seeded: dict[str, int],
    writer: Callable[[Callable[..., object]], None],
) -> None:
    """E9: путь в базе есть, файла на диске нет — это 404 (урок L1)."""

    async def _break_path(session: object) -> None:
        from sqlalchemy import update

        # Только свой артефакт: без условия ломался путь **каждому** файлу в
        # базе, включая настоящие кейсы, собранные руками.
        await session.execute(  # type: ignore[attr-defined]
            update(CaseArtifact)
            .where(CaseArtifact.case_id == seeded["case"])
            .values(path="/нет/такого/файла.pdf")
        )

    writer(_break_path)

    response = client.get(f"/api/cases/{seeded['case']}/download", headers=_token(client))
    assert response.status_code == 404


def test_usage_reports_spend_and_remaining(client: TestClient) -> None:
    """E10: потрачено, зарезервировано и остаток одним ответом."""
    body = client.get("/api/usage", headers=_token(client)).json()

    assert body["spent"] >= 0
    assert body["reserved"] >= 0
    assert body["remaining"] == 10_000  # fixture-остаток: бюджет первичного прогона
