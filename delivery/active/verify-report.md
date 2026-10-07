# Verify report: cli-commands-are-tested

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M68–M70 | `tests/test_cli_run_lock.py` (настоящий advisory-замок Postgres; провайдер подменён падением) | 3 passed; **до правки** M68 и M69 красные — консоль при идущем прогоне шла покупать (`AssertionError` подменного провайдера), M70 зелёный и до, и после |
| M71–M77 | `tests/test_cli_commands.py` (команды в процессе, своя версия порогов, коммиты и уборка своих строк) | 9 passed |
| M78 | `tests/test_ci_gates_judge.py` | 7 passed; мутант — вернуть шагу покрытия `continue-on-error`: красные и M78, и оракул срока отсрочки; workflow возвращён |
| Отказ кнопки | `tests/test_api_runs.py` | 33 passed: 409 тем же текстом, что прежде |
| Полный сьют с покрытием | `pytest --cov=src/ahrefs_cases` | 862 passed, 11 skipped; один красный — `test_every_declared_repro_test_exists` читал комментарий в строке `repro_test` STATUS — комментарий убран, тест зелёный. `cli/collect_commands.py` 41,7 → 93,6 %, `cli/case_commands.py` 60,5 → 87,3 %, `cli/source.py` 69,2 → 100 % |
| Типы | `mypy` strict (пакет и новые тесты) | чисто |

## Исполнение рисковых путей

- Консольная постановка под замком — прогнал `pytest tests/test_cli_run_lock.py` на дев-базе с настоящим
  `pg_advisory_xact_lock`, увидел: пока сессия «кнопки» держит замок постановки, консольный `_collect`
  стоит (через 0,5 с не завершён), после её коммита — отказ кодом 5 с номером открытой строки `queued`;
  новых строк прогона нет. at=2026-10-07

## Ревью рисковых мест

**Деньги.** Платящие команды консоли теперь спрашивают «прогон уже идёт» прямо перед сбором, в его
сессии: `if await _busy(session):` → `return _EXIT_BUSY` стоит перед `collect_all`, `collect_stage2` и
`collect_case_data`. Раньше консоль открывала прогон в обход проверки, и при идущем прогоне кнопкой оба
покупали одни и те же ряды. Тест M68 подменяет провайдер падением: отказ случается до покупки.

**Конкурентность.** Проверка одна на кнопку и консоль: `await hold_start(session)` и
`select(Run).where(Run.status.in_(ACTIVE_STATUSES))` в `claim_start`. Замок транзакционный, поэтому между
проверкой и коммитом строки прогона ничего не коммитит: `reap_stale_runs` пишет без коммита,
`system_user` — только `flush`, коммит — сразу после `open_run` (M69 это исполняет).

**Транзакция БД.** `claim_start` ничего не коммитит и живёт в транзакции вызывающего: у кнопки строку
открывает `open_run` и коммит идёт следом, как прежде; у консоли отказ — `return _EXIT_BUSY` внутри
`async with get_sessionmaker()() as session:`, сессия закрывается откатом, и замок постановки снимается
вместе с ней. Без отказа замок держится до коммита строки прогона в `collect_projects`.

**Ошибки.** Отказ — своё исключение, а не код по месту: `raise RunAlreadyActiveError(active)`; кнопка
переводит его в `HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))` — тем же текстом,
что прежде, консоль печатает его со следующим шагом и отдаёт код 5, отдельный от «прогон упал» (3).

**Безопасность.** Риска нет, потому что новых входов нет: права кнопки (`require_right("run")`) не
менялись, консоль — на сервере, под тем же замком.

**Производительность.** Проверка — один запрос по таблице прогонов с `LIMIT 1`, как прежде у кнопки; замок
консоль держит от проверки до коммита строки прогона — миллисекунды, а не время подсчёта кандидатов.

## Чего проверка НЕ доказывает

- Консоль на проде при идущем прогоне кнопкой — живьём не встречено (`observe_signal`).
- Две консоли одновременно — тот же замок и та же проверка; отдельного теста на пару консолей нет (M69 —
  кнопка против консоли).
- Покрытие измерено локально; в CI гейт судит изменённые файлы того же сьюта.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED


asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **68**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M78	assert judging, "шага покрытия изменённых файлов в CI нет"
M78	assert str(workflow.get("env", {}).get("STRICT")) == "1"
M78	assert [step.get("continue-on-error", False) for step in judging] == [False] * len(judging)
Z22	assert spec is not None
Z22	assert spec.loader is not None
Z22	assert ruleset is not None
M71	assert await collect_commands._intake(good) == 0
M71	assert "принято: 2 (создано 2, обновлено 0)" in capsys.readouterr().out
M71	assert await collect_commands._intake(broken) == 1
M71	assert "принято: 0" in told
M71	assert told.count(": period_start — ") == 2
M72	assert code == EXIT_RUN_FAILED
M72	assert f"в базе нет проектов: {MISSING}" in capsys.readouterr().err
M72	assert await _runs() == before
M73	assert await collect_commands._stage2(only=[DOMAIN]) == 0
M73	assert await collect_commands._case_data(only=[DOMAIN]) == 0
M73	assert "кандидатов нет: шаг 2 не нужен" in told
M73	assert "кейсов нет: «хороших» и «средних» по действующим порогам не найдено" in told
M73	assert await _runs() == before
M74	assert await collect_commands._classify(MetricSource.FIXTURE) == 0
M74	assert await collect_commands._recalc(RULESET, make_active=False) == 0
M74	assert await collect_commands._preview(RULESET) == 0
M74	assert await collect_commands._recalc("нет-такой", make_active=True) == EXIT_BAD_SOURCE
M74	assert await collect_commands._preview("нет-такой") == EXIT_BAD_SOURCE
M74	assert "пересчёт не выполнен: " in told
M74	assert "предпросмотр не выполнен: " in told
M75	assert await collect_commands._diagnose(MISSING) == EXIT_BAD_SOURCE
M75	assert f"проект не найден: {MISSING}" in capsys.readouterr().err
M75	assert await collect_commands._diagnose(DOMAIN) == 0
M75	assert "кампаний по домену: 2" in capsys.readouterr().out
M75	assert await collect_commands._diagnose(None) == 0
M75	assert "«плохих» проектов: 1" in capsys.readouterr().out
M75	assert await collect_commands._explain(DOMAIN) == 0
M75	assert f"кампаний по домену {DOMAIN}: 2" in told
M75	assert "✓" in told
M75	assert "✗" in told
M75	assert await collect_commands._diagnose(None) == 0
M75	assert "«плохих» проектов нет — диагностировать нечего" in capsys.readouterr().out
M76	assert await case_commands.show_cases(DOMAIN, None, MetricSource.FIXTURE) == 0
M76	assert f"{DOMAIN} — good, " in shown
M76	assert "1000 →       2000" in shown
M76	assert await case_commands.render_case(DOMAIN, MetricSource.FIXTURE) == 0
M76	assert f"{DOMAIN} → {out_dir}" in rendered
M76	assert "версия кейса 1" in rendered
M76	assert await case_commands.pack_cases(MetricSource.FIXTURE) == 0
M76	assert str(out_dir) in packed
M76	assert ".zip" in packed
M76	assert await case_commands.render_case(MISSING, MetricSource.FIXTURE) == EXIT_BAD_SOURCE
M76	assert f"проект не найден: {MISSING}" in capsys.readouterr().err
M76	assert await case_commands.pack_cases(MetricSource.FIXTURE) == EXIT_BAD_SOURCE
M76	assert capsys.readouterr().err.strip()
M77	assert source.named(argparse.Namespace(source="live")) is MetricSource.LIVE
M77	assert source.named(argparse.Namespace(source="fixture")) is MetricSource.FIXTURE
M77	assert source.named(argparse.Namespace()) is None
M77	assert source.reading_source(None) is MetricSource.FIXTURE
M77	assert source.reading_source(None) is MetricSource.LIVE
Z52	assert author is not None
Z52	assert ruleset is not None
M68	assert codes == [EXIT_BUSY, EXIT_BUSY, EXIT_BUSY]
M68	assert told.count(f"прогон {busy} ещё идёт (running); второй не запускается") == 3
M68	assert [one[0] for one in await _runs_after(before)] == [busy]
M69	assert author is not None
M69	assert waited, "консоль не ждала замка постановки: проверка шла мимо него"
M69	assert code == EXIT_BUSY
M69	assert f"прогон {opened} ещё идёт (queued); второй не запускается" in capsys.readouterr().err
M69	assert [one[0] for one in await _runs_after(before)] == [opened]
M70	assert code == 0
M70	assert [(status, email) for _, status, email in opened] == [(RunStatus.DONE, SYSTEM_USER_EMAIL)]
```

✅ **Каждое утверждение ведёт к примеру спеки** (M68 M69 M70 M71 M72 M73 M74 M75 M76 M77 M78 Z22 Z52), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 10 code (+17 process docs) / +594/-29 (net +565) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — .github/workflows/quality.yml, tests/cli_world.py (новый оракул), tests/test_cli_commands.py (новый оракул), tests/test_cli_run_lock.py (новый оракул) |
| implement_retries | 2 — первые тесты консоли на `db_session` зависли (`TRUNCATE` её транзакции держал сессии команд на замках таблиц) — переписаны на коммиты со своей версией порогов; точка вердикта в тесте M76 без `derived` — `VerdictFormatError` |
| verify_fails_before_green | 1 — полный сьют: `test_every_declared_repro_test_exists` читал комментарий в строке `repro_test` STATUS как имя теста |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
