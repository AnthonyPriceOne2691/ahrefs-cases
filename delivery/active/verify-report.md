# Verify report: collect-stops-on-failure

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M96 (repro) | `tests/test_collect_stop.py` (12 доменов, параллель 3, запись падает на третьем) | **до правки** красный: к сбою 6 запросов, после — 12, остаток списка докуплен; после — 6 и 6 |
| M97 | `tests/test_collect_stop.py` — задачи сбора на входе в `_fail_run` | после правки зелёный; опора фильтра по имени задачи — `test_task_name_is_real` |
| M98 | `tests/test_collect_stop.py` + `tests/collect_child.py` — SIGKILL дочернего сбора, пока третий запрос «в сети» | два домена записаны, висящего среди них нет; прогон `running` → реапер `failed`; повтор спрашивает только два остальных |
| Мутанты | A — без `cancel()`; C — без ожидания отменённых | A: M96 красный; C: M97 красный — после того, как фильтр задач перестал искать прежнее имя `_execute_tasks` (см. ниже); код возвращён |
| Сбор и консоль | `tests/test_collect_*`, `tests/test_cli_*` | 47 passed |
| Полный сьют | `pytest` | 881 passed, 12 skipped |
| Живой проход | стенд: копия базы `cases_geo`, воркер на коде ветки, Chrome по CDP | см. ниже |

## Исполнение рисковых путей

- Сбор через новый модуль в настоящем воркере — загрузил на стенде кнопкой «Загрузить файл» список из трёх новых
  доменов (`z52-alpha`, `-beta`, `-gamma`), «Весь цикл по этому списку» → «Запустить», увидел: прогон №2357
  «цикл по файлу — готов», «3 из 3», условные units 1 428 → 1 278, «Собрано 3 кейса», «Скачать 3 кейса». at=2026-10-08

## Что нашла проверка

- **Проверка «задач не осталось» была зелёной по построению.** Фильтр искал задачи по имени `_execute_tasks`, а
  после выноса цикла в `collect/execute.py` корутина зовётся `execute_tasks.<locals>.one`: фильтр не находил
  ничего и проходил при любом коде — мутант «отмена без ожидания» прошёл M97. Имя задачи — константа теста, а
  что задачи с ним вообще бывают, проверяет отдельный тест посреди живого сбора.
- **Проверка после `collect_all` не отличала «дождался» от «повезло»:** откат сессии в `_fail_run` уступает циклу
  событий, и отменённые задачи успевали закончиться сами. M97 смотрит на входе в `_fail_run`.

## Ревью рисковых мест

**Деньги.** Сбой цикла больше не оставляет покупателей: `for pending in running:` и `pending.cancel()` отменяют
и ждущие семафор, и ушедшие в сеть задачи, `await asyncio.gather(*running, return_exceptions=True)` дожидается
их до того, как ошибка пойдёт в `_fail_run`. Ушедший в сеть запрос (до `COLLECT_MAX_PARALLEL` = 3) на живом
ключе мог быть оплачен и теряется — та же граница, что у смерти процесса, она названа в Z52 и в
`ops/first-live-run.md`.

**Ошибки.** Обработчик `except BaseException:` всегда пробрасывает исходное исключение (`raise`), поэтому тип не
меняется: `_fail_run` пишет причину, как прежде, тесты C13 и C16 ловят `RuntimeError`. Отмена прогона снаружи
(`CancelledError`) проходит тем же путём и тоже не оставляет задач.

**Транзакция БД.** Риска нет, потому что задачи сбора сессию не трогают — пишет только цикл потребления
(`store_outcome`), и к `_fail_run` с его `session.rollback()` ни одна задача уже не жива.

**Безопасность.** Риска нет, потому что новых входов, прав и данных нет: меняется только остановка задач внутри
процесса сбора; дочерний процесс теста получает адрес той же дев-базы, что и сьют (`DATABASE_URL`).

**Производительность.** Риска нет, потому что задач столько же, сколько было: `as_completed` и прежде
создавал задачу на каждую корутину сразу, а теперь их создаёт `asyncio.create_task(one(task))` списком —
чтобы было что отменить; отмена и ожидание идут только на пути сбоя.

## Чего проверка НЕ доказывает

- Живой ключ: что Ahrefs не тарифицирует отменённый на лету запрос — не проверить без него; граница названа.
- Прод: упавший посреди сбора прогон на проде пока не встречался — наблюдение ждёт первого случая.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **11**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M96	assert len(failure.provider.calls) == failure.calls_at_failure
M97	assert left == [[]]
M97	assert seen and min(seen) >= 1
M98	assert child.stdout is not None
M98	assert line.startswith(IN_FLIGHT), f"дочерний сбор не дошёл до третьего запроса: {line!r}"
M98	assert child.returncode is None, "дочерний сбор кончился сам, до SIGKILL"
M98	assert (len(stored), hanging in stored) == (2, False)
M98	assert killed.status is RunStatus.RUNNING
M98	assert killed.id in await reap_stale_runs(session)
M98	assert killed.status is RunStatus.FAILED
M98	assert set(again.calls) == set(CRASH_DOMAINS) - stored
```

✅ **Каждое утверждение ведёт к примеру спеки** (M96 M97 M98), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 5 code (+16 process docs) / +427/-79 (net +348) |
| commits | 3 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/collect_child.py (новый оракул), tests/test_collect_stop.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.

