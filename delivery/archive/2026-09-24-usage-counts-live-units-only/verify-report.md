# Verify report: usage-counts-live-units-only

Verifier: human:anthony

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| R1: fixture-прогон не входит в «потрачено» и стоимость на сто | `pytest tests/test_api_usage.py::test_fixture_run_is_not_spent` | passed; **падал до правки** на `origin/main`: `assert 28066 == 27366` — «потрачено» выросло на 700 units fixture-прогона |
| R2: живой прогон — ровно своей суммой, его домен — в знаменатель | `pytest tests/test_api_usage.py::test_live_run_is_spent_exactly` | passed; до правки падал на `KeyError: 'live_domains'` — знаменателя в ответе не было (приращение «потрачено» на 300 было и до правки) |
| R3–R5, R8, R10: точные числа на пустой базе | `pytest tests/test_budget_spend.py` | passed (6 с R9) |
| R9: второй путь к сумме `SPENT` | `pytest tests/test_budget_spend.py::test_spend_is_summed_in_one_place` | passed; на `origin/main` назвал бы `api/routers/usage.py:41` — проверено тем же разбором AST по файлу из `origin/main` |
| R6, R7: экран | `vitest run src/pages/__tests__/ops.test.tsx` | 26 passed; R6 и R7 **падали до правки**: `Unable to find an element with the text: /^Условные units: 15 414 — /` и строка стоимости со слагаемыми |
| Вычет из остатка и прежние оракулы | `pytest tests/test_collect_quota.py tests/test_api_read.py tests/test_probe_next_day.py` | passed |
| Бэкенд целиком | `pytest -q` | 671 passed, 3 skipped |
| Фронт целиком | `vitest run` | 180 passed |
| Типы и стиль | `mypy src/ahrefs_cases`, `ruff check`, `ruff format --check`, `tsc --noEmit`, `eslint --max-warnings 0 src`, `prettier --check` | чисто |
| pre-commit | все хуки на коммитах поставки | Passed; `okf-sync` один раз отказал отдельному коммиту с правкой `budget.py` без концепта — правка слита с коммитом концепта |
| CI на ветке поставки | GitHub Actions, PR #22 | delivery, gates, tests — pass (672 passed, 2 skipped): https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36023066272 |

Прогон бэкенда параллельно с чужим `pytest` другой поставки на той же
дев-базе дал 2 failed и 11 errors: сторож вердиктов стенда увидел, что пропали
вердикты чужой тестовой версии порогов (`ruleset 914`), а тест карточки нашёл
`verdict: null` — действующую версию переключил чужой тест. Повтор без
соседа — зелёный (строка «Бэкенд целиком»).

## Исполнение рисковых путей

`web/src/pages/usage/` — копия дев-базы (`pg_dump` в `cases_usage_check`), API
из `origin/main` (`serve_api.py <old/src> 8791`) и из ветки
(`serve_api.py <worktree/src> 8792`) с `AHREFS_PROVIDER=fixture`, пустым
ключом и `QUEUE_BACKEND=inline`; боевые сборки обеих версий фронта
(`npx vite build`) под `VITE_API_URL=… npx vite preview`; headless Chrome 154
по CDP (`node drive_usage.cjs <base> <png>`), вход токеном проверяющего
`usage-check@local.test`. at=2026-09-24

| Число | SQL по журналу копии | Экран до правки | Экран после правки |
|---|---|---|---|
| потрачено | живые 11 952 (8 прогонов); весь `SPENT` 27 366 | «потрачено 27 366» | «потрачено 11 952» |
| условные units | fixture 15 413 + прогон без режима 1 = 15 414 | — | «Условные units: 15 414 — столько стоили бы прогоны без живого ключа (fixture)…» |
| знаменатель | оплачено живьём 62 домена; проектов 75 | 75 (не показан) | «оплачено доменов — 62» |
| стоимость на сто | 27 366 / 75 → 36 488; 11 952 / 62 → 19 277 | «36 488 units» | «19 277 units (потрачено 11 952 units, оплачено доменов — 62)» |
| резерв, остаток, неучтённое | 0; 10 000 (фикстура, ключа нет); 0 | 0; 10 000; — | 0; 10 000; — |

Тот же прогон на копии, где 8 живых прогонов помечены fixture (стенд без
живого ключа, как прод до перевода): после правки — «потрачено 0»,
«Условные units: 27 366 — …», «Стоимость запуска на сто доменов по факту пока не
из чего вывести: живых прогонов с расходом ещё не было»; до правки —
«потрачено 27 366» и «36 488 units».

Ответ API ветки на копии:
`{"spent":11952,"conditional":15414,"reserved":0,"remaining":10000,"uncounted":0,"live_domains":62,"per_hundred_domains":19277}`;
`origin/main`: `{"spent":27366,"reserved":0,"remaining":10000,"uncounted":0,"per_hundred_domains":36488}`.

После проверки: `DROP DATABASE cases_usage_check`, файл дампа в контейнере
удалён, два API, два `vite preview` и Chrome остановлены.

## Ревью рисковых мест

**Один снимок на три числа.** `spend_summary` считает живой расход, весь журнал
и оплаченные домены одним `SELECT` с `FILTER (WHERE …)` по `_live_run()`. Первая
редакция делала три запроса: в `READ COMMITTED` каждый видит свой снимок, и
строка живого прогона, записанная между суммой живых и суммой всех, попала бы в
`conditional` — экран чисто живого прода посреди прогона сказал бы «условные
units». Для `live_spend_since` та же живая выборка идёт через `_live(_spent(...))`
с `JOIN`: одно правило, две формы запроса, и R8 держит, что они совпадают.

**`outerjoin` против `join`.** В сводке журнал соединён с прогонами внешним
соединением: строка без прогона (`run_id` допускает `NULL`) или прогон без
режима в снимке дают `NULL` в `_live_run()`, `FILTER` их не берёт, а в общую
сумму они входят — значит попадают в условные units, а не теряются. R3 держит
это на прогоне без режима (1 unit).

**Знаменатель — `count(distinct target)`.** Домен считается один раз, сколько бы
ступеней воронки его ни прошли (R4), и только за живую оплату: строка `CACHED`
с тем же `target` в знаменатель не входит (R5). Удаление проекта журнал не
трогает — у `units_ledger` нет ключа на `projects`, — поэтому R10 держит
стоимость на сто неизменной; знаменатель по `run_items` менялся бы
(`ondelete=SET NULL`).

**Деньги.** Units — единственный платный ресурс, и поставка меняет то, как их
показывают, но не то, как их тратят. Решение «можно ли стартовать» принимает
preflight по `uncounted_spend` → `live_spend_since`, и его ответ не изменился:
та же выборка живых строк, теперь через `_live(_spent(_units()))` вместо
написанного на месте запроса; прежние оракулы `test_uncounted_counts_only_live_runs`
и `test_old_spend_falls_out_of_the_window` зелёные, R8 сверяет вычет со
сводкой. Цена отдельного прогона (`run_spend`) считается тем же каркасом
`_spent(_units())` по `run_id`, без правила режима — у прогона он один.
Остаток на экране не тронут (L117). Единственная точка отказа — сам
`_live_run()`: ошибись он, вычет и экран ошибутся одинаково, а не разойдутся, —
ради этого правило и собрано в одно место.

**Безопасность.** Право на экран не менялось: `router` в `usage.py` по-прежнему
висит на `Depends(require_right("read"))`. Слова `password`, `access_token`,
`Bearer`, `jwt_secret` в диффе — из теста `test_api_usage.py`: своя учётка
`usage-reader@test.local`, секрет подписи подменён `monkeypatch`, ничего из
этого не уходит в прод-код.

**Транзакции тестов.** `writer` в `test_api_usage.py` делает `commit` своих строк
в общую базу: прогоны своего пользователя в статусе `DONE` (не держат замок
«один активный прогон» и не входят в `reserved_units`), уборка — `delete_owned`
по пользователю и доменам. Точные числа — в `test_budget_spend.py` на
`db_session`: `TRUNCATE` внутри транзакции с откатом.

**Новые модули** — только тесты (`test_api_usage.py`, `test_budget_spend.py`);
новых модулей кода нет.

## Чего проверка НЕ доказывает

**Живые числа прода.** По данным координатора, прод с 24.09.2026 в `live`:
4 прогона, 10 460 units, 53 проекта, оплачено 51 домен, экран показывает
19 736 на сто доменов. После выкладки должно стать 20 510 (10 460 / 51), а
«потрачено» — 10 460, если все четыре прогона живые. На проде не проверялось:
ssh вне рамок поставки; это `observe_signal`.

**Мутационный гейт в CI не судил, diff-coverage ниже цели по одному файлу.** `mutmut 3.8.0` завершился с кодом 1 («гейт не судит») — так же, как в PR #18, то есть до этой поставки. Diff-coverage (информационный шаг) показал `usage.py` 60 % при цели 70 %; локально `pytest tests/test_api_usage.py --cov` даёт 90 % (не исполнена только ветка `except` при неузнанном остатке), а у `users.py` в PR #18 было 61,5 % — занижение покрытия роутеров в CI общее, не от этой правки.

**Тест экрана на общей базе меряет приращение.** Чужая запись в журнал между
двумя замерами сдвинула бы разницу; окно — доли секунды.

**Цену отдельного прогона и «что покупали по домену»** поставка не трогала —
см. открытые вопросы в `spec.md`.

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **29**, из них без ссылки на пример спеки:
**0**.

```
R1	assert after["spent"] == before["spent"]
R1	assert after["per_hundred_domains"] == before["per_hundred_domains"]
R1	assert after["live_domains"] == before["live_domains"]
R1	assert after["conditional"] - before["conditional"] == 700
R2	assert after["spent"] - before["spent"] == 300
R2	assert after["live_domains"] - before["live_domains"] == 1
R2	assert after["conditional"] == before["conditional"]
R2	assert after["per_hundred_domains"] == round(after["spent"] / after["live_domains"] * 100)
R3	assert spend.live == 300
R3	assert spend.conditional == 501
R3	assert spend.live_domains == 2
R3	assert spend.per_hundred() == 15_000
R4	assert spend.live_domains == 2
R4	assert spend.per_hundred() == 25_000
R5	assert only_fixture.live == 0
R5	assert only_fixture.per_hundred() is None
R5	assert cached_only.live_domains == 0
R5	assert cached_only.per_hundred() is None
R8	assert deduction == spend.live == 900
R10	assert after == before
R10	assert after.per_hundred() == 30_000
R9	assert not stray, (
R9	assert "collect/budget.py" in readers
R6	expect(await screen.findByText('потрачено 0')).toBeInTheDocument();
R6	expect(screen.getByText(/^Условные units: 15 414 — /)).toBeInTheDocument();
R6	expect(screen.getByText(/живых прогонов с расходом ещё не было/)).toBeInTheDocument();
R6	expect(screen.queryByText(/прогонов не было/)).not.toBeInTheDocument();
R7	expect(
R7	expect(screen.queryByText(/Условные units/)).not.toBeInTheDocument();
```

Примеры R1–R10 написал исполнитель под слово владельца «поправь расхождение»;
знаменатель и R10 уточнены сообщением координатора (удаление проектов готовится
параллельно). Подпись проверяющего под ними — на handoff.

asserts_without_example: 0

## Verdict
- [x] READY FOR HANDOFF — ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 8 code (+9 process docs) / +656/-52 (net +604) |
| commits | 2 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_api_usage.py (новый оракул), tests/test_budget_spend.py (новый оракул) |
| implement_retries | 3 — mypy (`Any` из JSON-пути в `_live_run`, `Select[tuple[int | None]]` у суммы), eslint `max-lines-per-function` 105 > 80 и prettier на тестах экрана, `okf-sync` на отдельном коммите с `budget.py` без концепта; плюс переделка знаменателя по сообщению координатора (проекты `run_items` → оплаченные домены) |
| verify_fails_before_green | 0 по продуктовым оракулам после правки; один прогон бэкенда красный по окружению — параллельный `pytest` другой поставки на той же дев-базе (2 failed, 11 errors), повтор без соседа зелёный |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
