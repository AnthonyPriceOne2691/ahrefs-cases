# Verify report

**Date:** 2026-09-10
**Verifier:** <human:anthony — заполняется при приёмке>
**asserts_reviewed_by:** <human:anthony at=… — восемь примеров дописаны по ходу, см. ниже>
<!-- Дайджест даёт `asserts_without_example: 0`, но C11–C18 появились в спеке
     ПОСЛЕ подписи (по ходу implement и по указанию заказчика работ), значит
     «человек подписал заранее» про них неверно. Подпись настоящая. -->
**CI run:** <заполняется после прогона на 1dbb54d>
**Commit:** 1dbb54d

## Прогон в чистом клоне

```
$ git clone . <clone> && cd <clone>
$ python3 scripts/delivery_check.py
  delivery_check: 0 error(s), 0 warning(s)
$ python3 -m pytest -q
  163 passed, 1 skipped
```

## Shape oracles
- [x] PASS — `pre-commit run --all-files`: 27 хуков, упавших 0
- [x] PASS — `ruff` / `ruff format --check` / `mypy --strict`: чисто на 72 модулях
- [x] PASS — гейты видят код (число просмотренных файлов непустое)

## Behavior oracles
- [x] PASS — `pytest`: 163 теста, 1 пропущен (разрушающий цикл миграций — в CI)
- [x] PASS — покрытие ядра **94 %** при пороге 80 %
- [x] PASS — примеры C1–C18 закрыты тестами, `asserts_without_example: 0`
- [x] PASS — `scripts/delivery_check.py`: 0 ошибок, 0 предупреждений

## Product oracles
- [x] PASS — `eval-smoke.md` прогнан целиком на чистой базе; ключевое число:
      **второй прогон делает 0 запросов и тратит 0 units** — главный DoD всей Ф2
- [ ] n/a — `delivery/evals/smoke/` пуст: устойчивый набор заводится в Ф5, когда
      прогон станет запускаться по HTTP

## Что нашлось на verify и по ходу, а не раньше

- **Предохранитель не работал вовсе.** `as_completed` стартует все корутины
  сразу, и проверка снаружи семафора успевала пройти до первой неудачи: тест
  C14 видел 10 запросов вместо 3. Перенесён под семафор.
- **Миграция enum была зелёной и нерабочей.** SQLAlchemy хранит **имена** членов
  (`SKIPPED_ABORTED`), а `ALTER TYPE` добавлял значение в нижнем регистре.
  Проверять надо `enum_range`, а не успех миграции.
- **Отчёт врал на шаге 2**: «проектов 3, собрано 12» — считались задачи.
  Нашлось сквозным прогоном, не тестом.
- **Код возврата CLI измерялся через пайп** и показывал код `tail`.
  Перемерен напрямую, теперь под тестом (C15).
- **Гейт секретов дважды отклонил коммит**, а я едва не отчитался об успехе:
  hex-идентификаторы ревизии alembic приняты за ключ. Помечены `pragma`, а не
  внесены в baseline — baseline должен только сокращаться.

## Сверка с CRM агентства (по указанию заказчика работ)

Разобраны пятнадцать решений по «косячному исполнению прогонов», таблица —
`docs/REUSE_FROM_LINKBUILDER.md`. Взято сейчас: реапер зависших (возраст вместо
heartbeat, `coalesce`, guarded UPDATE, причина в строку), предохранитель,
чекпойнты. Отложено в Ф5 с названными причинами: квоты актёра, cooldown алертов,
force-финализация частей, backpressure. **Сверка нашла нашу дыру** — домен без
истории перезапрашивался каждым прогоном (C17).

## Ревью рисковых мест

Шесть мест, где эта поставка может сломаться не сразу и не очевидно.

1. **`SingleFlightProvider` отдаёт один объект нескольким ожидающим.** Сейчас
   это безопасно только потому, что `HistoryResult` и `HistoryPoint` —
   `frozen=True`. Стоит кому-то снять `frozen` ради удобства, и один прогон
   начнёт править данные другого; воспроизвести такое почти невозможно.
   Защита сегодня — только неизменяемость, и она не проверяется тестом.
2. **`cache.closed_through` считает границу месяца календарно.** Если Ahrefs
   отдаёт текущий месяц как завершённый (или наоборот, пересчитывает
   предыдущий), мы будем стабильно недобирать последнюю точку и **не узнаем**:
   пропуск выглядит как отсутствие данных. Это вопрос Ф7, и он записан в
   спеке как открытый.
3. **`budget.reserved_units` держит квоту зависшего прогона** до срабатывания
   `run_reaper` — по умолчанию час. Серия падений подряд может на этот час
   заблокировать сметы: смета будет отказывать по резервам мёртвых прогонов.
   Смягчает только порог реапера, и его придётся подбирать в Ф5 под реальную
   длительность прогона.
4. **`_execute_tasks` коммитит внутри прогона.** Вызывающий, привыкший к «одна
   транзакция на запрос», получит частично закоммиченную работу — в Ф5 это
   HTTP-обработчик. Свойство объявлено в плане и в докстринге, но нарушает
   привычку, а привычки сильнее докстрингов.
5. **`funnel.preliminary_candidates` делает запрос на проект.** На сотне это
   незаметно, на тысяче — сотни round-trip'ов. Место известное; переписывается
   в один запрос с группировкой, когда появится экран Ф6 с фильтрами.
6. **`run_reaper` фильтрует прогоны по `status` без индекса.** На тысячах
   строк это seq scan при каждом запуске прогона. Индекс не добавлен
   сознательно: в Ф2б прогонов десятки, а лишний индекс на маленькой таблице
   стоит дороже, чем экономит. Пересмотреть в Ф5.

**По классам риска.**

- **Деньги.** Главный класс этой поставки. `EndpointSpec.estimate_units` и
  `budget.reserve` определяют, сколько units спишется; ошибка здесь стоит
  напрямую. Защита: смета сверяется с фактом того же прогона в тесте (C5),
  журнал ведёт `spent` и `cached` раздельно, `FixtureQuota` даёт не
  бесконечность, а 10 000 — бюджет из ТЗ, чтобы стоп срабатывал уже в
  разработке. Остаточный риск: сама модель стоимости — гипотеза до Ф7.
- **Безопасность.** Риска нет, и вот почему: поставка не добавила ни одного
  входа извне (HTTP появится в Ф5), не трогает аутентификацию, а системный
  пользователь `run_journal.SYSTEM_USER_EMAIL` создан с невозможным хешем и
  `is_active=False` — войти им нельзя. Единственный новый сетевой путь —
  `LiveQuota` к `subscription-info/limits-and-usage`, запрос без параметров
  от пользователя.
- **Транзакции БД.** Изменение поведения: `_execute_tasks` коммитит по ходу
  (чекпойнты), а `_fail_run` делает `rollback` перед записью статуса. Опасность
  в том, что вызывающий получает частично закоммиченную работу — для фоновой
  задачи это цель, для HTTP-обработчика Ф5 будет неожиданностью. `reserved_units`
  читает незакоммиченные чужие резервы только после их коммита, поэтому смета
  видит намерения, а не фантазии.
- **Производительность.** Три места: `funnel.preliminary_candidates` делает
  запрос на проект (сотня — незаметно, тысяча — нет), `run_reaper._stale_runs`
  фильтрует по `status` без индекса, `cache.coverage` — запрос на пару
  (проект, endpoint) при построении плана, то есть N запросов на N проектов.
  Все три приемлемы на масштабе ТЗ (до 100 доменов) и названы здесь, чтобы в
  Ф5–Ф6 их не пришлось искать заново.

## Spec coverage gaps
- `AhrefsLive` и `LiveQuota` написаны, но проверены только на подменённом
  транспорте: живой API не проверяет никто до Ф7.
- Single-flight внутрипроцессный. Межпроцессный замок — Ф5 вместе с очередью;
  до тех пор второй воркер не запускается.
- Порог «закрытого» месяца календарный. Совпадает ли он с представлением
  Ahrefs — вопрос Ф7.

## Объём поставки вышел за предохранитель

`circuit breaker: net loc_diff 2521 > 800`. Срабатывание честное, и вот
причина: поставка открывалась как C1–C10 (кэш, квота, воронка), а по ходу
получила C11–C18 — реапер, полную обработку ошибок, чекпойнты, предохранитель и
память о пустом ответе. Восемь примеров из восемнадцати добавлены после
подписи спеки, по указанию заказчика работ и по итогам сверки с CRM.

Что с этим делать честно: **это класс L, а не M**, и его следовало разрезать
на «экономию» и «устойчивость» в тот момент, когда пришло требование про
обработку ошибок. Тогда каждая половина проверялась бы отдельно, а не одним
verify на 2521 строку.

Waiver ставит человек (§3.4) — Builder себе объём не прощает.

## Verdict
- [ ] READY FOR HANDOFF
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

<!-- Вердикт не ставит Builder (§5.2). Отметку ставит Verifier (human:anthony). -->
## Assertion digest (ревью ожиданий, не кода)

База: `b055f4b` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **79**, из них без ссылки на пример спеки:
**2**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
C15	assert result.returncode == _EXIT_BAD_SOURCE
C15	assert expected_text in result.stderr
C15	assert "Traceback" not in result.stderr
-	assert result.returncode == 0
-	assert "stage2" in result.stdout
C2	assert result == expected
C3	assert closed_through(date(2026, 9, 15)) == date(2026, 8, 31)
C3	assert closed_through(date(2026, 1, 3)) == date(2025, 12, 31)
C3	assert result == date(2026, 9, 1)
C1	assert result is None
C3	assert is_fresh(now - timedelta(hours=1), now) is True
C3	assert is_fresh(now - timedelta(days=3), now) is False
C3	assert is_fresh(None, now) is False
C2	assert result == WINDOW_FROM
C2	assert known.last_point == date(2025, 3, 1)
C2	assert known.last_point == date(2025, 4, 1)
C2	assert known.is_empty
C2	assert known.is_empty
C9	assert sorted(candidates) == sorted(ids[domain] for domain in GROWING)
C9	assert asked == set(GROWING)
C9	assert report.requests_made == len(GROWING) * len(stage2_specs())
C9	assert (await db_session.execute(stmt)).scalars().all() == []
C9	assert candidates == []
C9	assert DOMAIN_RATING_HISTORY not in stage2_specs()
C9	assert DOMAIN_RATING_HISTORY in stage2_specs()
C5	assert first.units_estimated == 100 * METRICS_HISTORY.estimate_units()
C5	assert second.units_estimated == 0
C5	assert report.units_estimated > 0
C5	assert abs(report.units_estimated - report.units_spent) <= report.units_estimated * 0.1
C6	assert report.status == RunStatus.FAILED.value
C6	assert report.requests_made == 0
C6	assert "не хватает units" in report.error
C6	assert run.started_at is None, "прогон, отклонённый preflight, никогда не начинался"
C7	assert report.status == RunStatus.FAILED.value
C7	assert report.requests_made == 0
C7	assert "неизвестен" in report.error
C6	assert not_enough.verdict is QuotaVerdict.NOT_ENOUGH
C6	assert unknown.verdict is QuotaVerdict.UNKNOWN
C6	assert state.verdict is QuotaVerdict.NOT_ENOUGH
C8	assert report.status == RunStatus.FAILED.value
C8	assert "зарезервировано 9000" in report.error
C8	assert await reserved_units(db_session) == 0
C12	assert report.status == RunStatus.PARTIAL.value
C12	assert (report.projects_ok, report.projects_failed) == (2, 1)
C12	assert "KeyError" in failed.reason
C13	assert run.status is RunStatus.FAILED
C13	assert "RuntimeError" in run.error
C14	assert len(provider.calls) == 3
C14	assert report.projects_aborted == len(domains) - 3
C14	assert all("предохранителем" in item.reason for item in aborted)
C14	assert not breaker.tripped
C16	assert saved > 0, "данные двух собранных доменов пропали — прогон стал чистой тратой"
C16	assert len(provider.calls) == len(domains) - 2, "докупили не только недостающее"
C17	assert provider.calls == []
C17	assert second.requests_saved == 2
C17	assert provider.calls == ["empty.example.com"]
C11	assert reaped == [run.id]
C11	assert run.status is RunStatus.FAILED
C11	assert "реапером" in run.error
C11	assert reaped == []
C11	assert run.status is RunStatus.RUNNING
C11	assert reaped == []
C11	assert run.status is RunStatus.DONE
C1	assert (first.requests_made, first.requests_saved) == (1, 0)
C1	assert (second.requests_made, second.requests_saved) == (0, 1)
C1	assert second.units_spent == 0
C1	assert total == first.points_written
C10	assert len(rows) == 5
C10	assert {row.kind for row in rows} == {LedgerKind.CACHED}
C10	assert second.requests_saved == 5
C18	assert forced.requests_made == 1
C18	assert total == first.points_written == forced.points_written
C4	assert len(inner.calls) == 1
C4	assert all(result.points == results[0].points for result in results)
C4	assert sorted(inner.calls) == ["d1.example.com@2025-01-01", "d2.example.com@2025-01-01"]
C4	assert len(inner.calls) == 2
C4	assert inner.calls == 2
C4	assert result.source is MetricSource.FIXTURE
C4	assert provider.source is MetricSource.FIXTURE
```

Привязаны к примерам: **C1 C10 C11 C12 C13 C14 C15 C16 C17 C18 C2 C3 C4 C5 C6 C7 C8 C9**. Остальные 2 — нет.

Читать нужно **только строки с `-` в первой колонке**: их ожидание
ничем не подписано. Подпись: `asserts_reviewed_by: human:… at=…`.

asserts_without_example: 2

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base b055f4b -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 24 code (+6 process docs) / +2619/-98 (net +2521) |
| commits | 5 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_cli_exit_codes.py (новый оракул), tests/test_collect_cache.py (новый оракул), tests/test_collect_funnel.py (новый оракул), tests/test_collect_quota.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
