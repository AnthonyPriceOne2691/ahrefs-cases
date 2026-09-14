"""Команды прогона: приём, сбор, классификация, пересчёт, разбор.

Вынесены из `scripts/run_collect.py`, когда тот перевалил лимит длины файла
(500 строк). Деление не косметическое: в скрипте остаётся **разбор аргументов и
диспетчер** — то, что зависит от командной строки, — а здесь живут сами
операции, которые зовёт ещё и воркер.

Правила, которые здесь держатся:

- **источник рядов называет вызывающий** (`cli.source`) — умолчание трижды
  давало молчаливую пустоту в живом режиме (урок L53), а правило, применённое
  к трём командам вместо класса команд, заставило поднимать живой режим ради
  чтения уже купленного (урок L142);
- **домен приводится к канону тем же нормализатором, что приём** (`_canonical`):
  человек набирает домен так, как видит его в своём файле (урок L124);
- **у платящей команды есть область действия** (`_scoped_projects`): без неё
  прогон платит за всё, что найдёт в базе (урок L111).
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from sqlalchemy import select
from sqlalchemy.engine import ScalarResult
from sqlalchemy.ext.asyncio import AsyncSession

from ahrefs_cases.classify.candidates import stage2_candidates
from ahrefs_cases.classify.diagnose import diagnose_domain, diagnose_poor
from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import activate, recalc
from ahrefs_cases.classify.rulesets import active_ruleset, seed_thresholds
from ahrefs_cases.classify.thresholds import ThresholdsError
from ahrefs_cases.classify.verdicts import classify_all, classify_project
from ahrefs_cases.classify.windows import point_windows
from ahrefs_cases.cli.source import provider_source, reading_source
from ahrefs_cases.collect.runner import collect_all, collect_case_data, collect_stage2
from ahrefs_cases.intake.accept import (
    SourceNotFoundError,
    UnknownSourceError,
    accept,
    read_source,
)
from ahrefs_cases.intake.gsheet_source import SheetAccessError, SheetLinkError
from ahrefs_cases.intake.normalize import DomainRejected, normalize_domain
from ahrefs_cases.storage._enums import Group, MetricSource
from ahrefs_cases.storage.models.project import Project
from ahrefs_cases.storage.models.ruleset import Ruleset
from ahrefs_cases.storage.models.verdict import Verdict
from ahrefs_cases.storage.session import get_sessionmaker

_SOURCE_ERRORS = (SourceNotFoundError, UnknownSourceError, SheetLinkError, SheetAccessError)
_EXIT_BAD_SOURCE = 2
_EXIT_RUN_FAILED = 3
_EXIT_CONTENT_BLOCKED = 4
_EXIT_INTERRUPTED = 130


async def _intake(reference: str) -> int:
    """Приём одного источника. Ошибка источника — сообщение, а не трассировка.

    Опечатка в пути и закрытая таблица — самые частые ошибки запуска, и
    отвечать на них стеком `io.open` значит требовать от человека читать
    трассировку ради строки «файла нет».
    """
    try:
        table = read_source(reference)
    except _SOURCE_ERRORS as exc:
        print(f"источник не прочитан: {exc}", file=sys.stderr)
        return _EXIT_BAD_SOURCE

    async with get_sessionmaker()() as session:
        report = await accept(session, table)
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.accepted else 1


class OnlyNotADomainError(ValueError):
    """В `--only` названо то, что доменом не является."""


def _only(raw: str | None) -> list[str] | None:
    """Список доменов из `--only`: перечисление через запятую или файл со списком.

    Файл — потому что боевой список приходит файлом, и перепечатывать сотню
    доменов в командную строку никто не станет. Пусто — значит все проекты
    базы, и это отдельное решение человека, а не умолчание «на всякий случай».

    **Имена приводятся к канону тем же вызовом, что и приём.** В базе лежит
    канонический хост: `ПРОВЕРКА-Рост.example` приём превратил в
    `xn----7sbfmzvfbjddnn.example`, а фильтр сравнивал строку как её набрали — и
    отвечал «в базе нет проектов» на проект, созданный минуту назад из того же
    файла. Канон домена знает `intake.normalize`, значит тот, кто называет
    домен снаружи, обязан позвать его же: двух правил соответствия имён быть
    не должно.
    """
    if not raw:
        return None
    path = Path(raw)
    if path.is_file():
        names = _names_in(path.read_text(encoding="utf-8"))
    else:
        names = [name.strip() for name in raw.split(",")]
    return [_canonical(name) for name in names if name]


def _names_in(text: str) -> list[str]:
    """Домены из файла: список построчно **или** колонка `domain` файла приёма.

    Оператор загружает список файлом — это боевой сценарий, — и тот же файл
    естественно подставляет в `--only`, чтобы прогон шёл ровно по нему. Раньше
    это отказывало на строке заголовков: «`domain,period_start,…`: не домен».
    Сообщение честное и бесполезное — человек видит свою же первую строку и не
    понимает, чего от него хотят.

    Разделитель ищется тот же, что у приёма (`csv.Sniffer`), а не
    предполагается запятой: агентство выгружает из Excel, и там бывает `;`.
    """
    first = text.splitlines()[0] if text.strip() else ""
    if "domain" not in first.lower() or not any(sep in first for sep in ",;\t"):
        return [line.strip() for line in text.splitlines()]
    reader = csv.DictReader(io.StringIO(text), dialect=csv.Sniffer().sniff(first))
    column = next(
        (name for name in reader.fieldnames or () if name.strip().lower() == "domain"), None
    )
    if column is None:
        return [line.strip() for line in text.splitlines()]
    return [str(row.get(column) or "").strip() for row in reader]


def _named(domain: str | None) -> str | None:
    """Домен из аргумента команды — к канону, `None` остаётся `None`.

    Отдельная обёртка, потому что у `render`, `explain`, `diagnose` и `cases`
    домен необязателен: без него команда работает по всем проектам. Приводить
    `None` нельзя, а забыть привести строку — тот же дефект, что был у `--only`
    (урок L124): человек набирает домен так, как видит его в своём файле.
    """
    return None if domain is None else _canonical(domain)


def _canonical(name: str) -> str:
    """Имя из `--only` → канонический хост, или отказ с причиной.

    Отказ здесь — исключение, а не значение (в отличие от приёма): в списке на
    сотню доменов одна плохая строка пропускается с пометкой, а в `--only`
    человек называет ровно то, что хочет собрать. Пропустить названное молча
    значит собрать не то, о чём просили.
    """
    canonical = normalize_domain(name)
    if isinstance(canonical, DomainRejected):
        message = f"{name}: не домен ({canonical.reason.value})"
        raise OnlyNotADomainError(message)
    if canonical != name:
        # Превращение показывается, иначе человек не поймёт, почему в отчёте
        # прогона другое имя, чем он набрал.
        print(f"домен приведён к канону: {name} → {canonical}")
    return canonical


async def _collect(*, refresh: bool = False, only: list[str] | None = None) -> int:
    async with get_sessionmaker()() as session:
        if only is not None:
            print(f"собираем только названные домены: {len(only)}")
        report = await collect_all(
            session, refresh=refresh, windows=await point_windows(session), only=only
        )
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


async def _stage2(*, refresh: bool = False, only: list[str] | None = None) -> int:
    """Шаг 2 воронки по предварительным кандидатам.

    Кандидатов считает **классификация** (`classify.candidates`): кандидат — тот,
    кого действующие пороги уже не считают «плохим» по данным шага 1. Раньше
    здесь стоял отдельный префильтр, который мерил рост крайними точками ряда, —
    и на сезонных сайтах расходился с вердиктом вдвое, отсекая от подтверждающих
    метрик тех, кто по порогам обязан был их получить (калибровка 14.09.2026).

    `only` сужает до названных доменов — по той же причине, что у `collect`
    (урок L111): рядом с боевым списком на стенде живут отладочные проекты, и
    шаг 2 — самая дорогая ступень. Без области действия он платит за всех,
    кого найдёт в базе.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        projects = list((await _scoped_projects(session, only)).all())
        candidates = await stage2_candidates(session, projects, source=provider_source())
        if not candidates:
            print("кандидатов нет: шаг 2 не нужен — за «плохих» дорогие метрики не платятся")
            return 0
        print(f"кандидатов: {len(candidates)} из {len(projects)}")
        report = await collect_stage2(
            session, candidates, refresh=refresh, windows=await point_windows(session)
        )
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


async def _scoped_projects(session: AsyncSession, only: list[str] | None) -> ScalarResult[Project]:
    """Проекты прогона: названные или все.

    Область действия — общая забота всех платящих команд, поэтому и вычисляется
    одинаково. `collect` получил её 12.09.2026 после того, как живой прогон ушёл
    в Ahrefs за отладочными доменами стенда (урок L111); `stage2` и `case-data`
    остались без неё, хотя платят больше: шаг 2 — самая дорогая ступень.
    """
    stmt = select(Project)
    if only is not None:
        stmt = stmt.where(Project.domain.in_(only))
    return (await session.execute(stmt)).scalars()


async def _case_data(*, refresh: bool = False, only: list[str] | None = None) -> int:
    """Ступень кейса: докупить кривую позиций и стоимость трафика.

    Только тем, у кого кейс будет, — проектам с вердиктом `good` или `medium`
    по действующей версии порогов. «Плохие» и «данных не хватает» не стоят
    ничего: в этом и смысл ступени.
    """
    async with get_sessionmaker()() as session:
        stmt = (
            select(Verdict.project_id)
            .join(Ruleset, Ruleset.id == Verdict.ruleset_id)
            .join(Project, Project.id == Verdict.project_id)
            .where(Ruleset.is_active.is_(True), Verdict.group.in_([Group.GOOD, Group.MEDIUM]))
        )
        if only is not None:
            stmt = stmt.where(Project.domain.in_(only))
        ids = list((await session.execute(stmt)).scalars().all())
        if not ids:
            print("кейсов нет: «хороших» и «средних» по действующим порогам не найдено")
            return 0
        print(f"проектов с кейсом: {len(ids)}")
        report = await collect_case_data(
            session, ids, refresh=refresh, windows=await point_windows(session)
        )
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.projects_ok else 1


async def _classify(chosen: MetricSource | None = None) -> int:
    """Классификация по действующей версии порогов.

    Ahrefs не трогается: считаем по тому, что уже куплено — и поэтому источник
    рядов называет вызывающий, а не режим провайдера. Пересчитать вердикты по
    уже купленным живым рядам можно, не открывая доступ к живому ключу (Z11).

    Если активной версии порогов нет — сеем её из `config/thresholds.example.yml`,
    потому что первый запуск на пустой базе иначе упирается в ошибку там, где
    достаточно дефолтов Приложения А.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        report = await classify_all(session, source=reading_source(chosen))
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.total else 1


async def _recalc(version: str, *, make_active: bool, chosen: MetricSource | None = None) -> int:
    """Пересчёт по указанной версии порогов. Ahrefs не трогается.

    Нужен калибровке: заказчик правит пороги по десяти доменам с экспертной
    оценкой и смотрит, что изменилось. Прошлые вердикты остаются на месте —
    вопрос «почему тогда было good» обязан иметь ответ.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        try:
            if make_active:
                await activate(session, version)
            report = await recalc(session, version, source=reading_source(chosen))
        except ThresholdsError as exc:
            print(f"пересчёт не выполнен: {exc}", file=sys.stderr)
            return _EXIT_BAD_SOURCE
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0 if report.recalculated else 1


async def _preview(version: str, chosen: MetricSource | None = None) -> int:
    """Что даст версия порогов, если её применить. Ничего не меняет.

    Нужна калибровке: заказчик правит порог, смотрит последствия, спорит,
    правит снова. Отвечать на это записью вердиктов значит смотреть на уже
    изменённое и откатывать руками.
    """
    async with get_sessionmaker()() as session:
        await seed_thresholds(session)
        try:
            report = await preview(session, version, source=reading_source(chosen))
        except ThresholdsError as exc:
            print(f"предпросмотр не выполнен: {exc}", file=sys.stderr)
            return _EXIT_BAD_SOURCE
        await session.commit()
    print("\n".join(report.as_lines()))
    return 0


async def _diagnose(domain: str | None, chosen: MetricSource | None = None) -> int:
    """Диагностика «плохих»: что просело, когда началось, потеряны ли домены.

    По ТЗ кейс «плохим» не формируется, но список с краткой причиной нужен для
    внутреннего анализа. Ahrefs не трогается, в базу ничего не пишется.
    """
    async with get_sessionmaker()() as session:
        if domain is not None:
            campaigns = await diagnose_domain(session, domain, source=reading_source(chosen))
            if not campaigns:
                print(f"проект не найден: {domain}", file=sys.stderr)
                return _EXIT_BAD_SOURCE
            if len(campaigns) > 1:
                print(f"кампаний по домену: {len(campaigns)}")
            for one in campaigns:
                print("\n".join(one.as_lines()))
            return 0

        found = await diagnose_poor(session, source=reading_source(chosen))
    if not found:
        print("«плохих» проектов нет — диагностировать нечего")
        return 0
    print(f"«плохих» проектов: {len(found)}")
    for item in found:
        print("\n".join(item.as_lines()))
    return 0


async def _explain(domain: str, chosen: MetricSource | None = None) -> int:
    """Показать вердикт одного домена со всеми условиями.

    Нужна не для отладки, а для калибровки: заказчик сверяет группу с
    экспертной оценкой и должен видеть, какое условие её определило.
    """
    async with get_sessionmaker()() as session:
        # Все кампании домена, а не первая попавшаяся: агентство ведёт сайт
        # несколькими периодами, и раньше команда молча показывала одну из них —
        # какую именно, зависело от порядка строк в базе.
        projects = list(
            (
                await session.execute(
                    select(Project).where(Project.domain == domain).order_by(Project.period_start)
                )
            )
            .scalars()
            .all()
        )
        if not projects:
            print(f"проект не найден: {domain}", file=sys.stderr)
            return _EXIT_BAD_SOURCE
        ruleset = await active_ruleset(session)
        verdicts = [
            (
                project,
                await classify_project(session, project, ruleset, source=reading_source(chosen)),
            )
            for project in projects
        ]
        await session.commit()

    if len(verdicts) > 1:
        print(f"кампаний по домену {domain}: {len(verdicts)}")
    for project, decision in verdicts:
        period = f"{project.period_start:%Y-%m} — {project.period_end:%Y-%m}"
        print(
            f"{domain} [{period}]: {decision.group.value} "
            f"(пороги {ruleset.version}, score {decision.score:.0f})"
        )
        for reason in decision.reasons:
            mark = "✓" if reason.passed else "✗"
            weight = "решает" if reason.decisive else "справочно"
            fact = "—" if reason.fact is None else f"{reason.fact:.1f}"
            threshold = "—" if reason.threshold is None else f"{reason.threshold:.1f}"
            print(
                f"  {mark} {reason.subject:34} факт {fact:>10}  "
                f"порог {threshold:>10}  [{weight}] {reason.note}"
            )
    return 0
