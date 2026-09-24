# Verify report: cases-stage-journal

**Date:** 2026-09-25
**Verifier:** human:anthony (приёмка); оракулы и исполнение на копии базы — agent:claude
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36061022773
**Commit:** 4b98af8

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| Y1–Y5, Y7–Y9 до правки | `pytest tests/test_cases_journal.py tests/test_collect_run.py::test_cases_stage_does_not_break_empty_memory tests/test_cases_builder.py::test_mismatch_advice_is_the_verdicts_own_rows` на коммите красных тестов (правки нет), своя копия базы `cases_casestage_tests` | 8 failed по причине дефекта: Y1 — `assert 0 == 1` (`projects_ok` 0); Y2, Y3 — `KeyError` (судеб нет); Y7 — «готов кейс journal-good.example — Кейс v1.pdf» вместо пачки; Y8 — тот же «готов кейс» без пачки; Y9 — «готов кейс wineverygame.com — Кейс v43.pdf» вместо отказа; Y4 — совет «перезапустите `classify` по этому источнику». Y5 — `AttributeError: CASE_NO_VERDICT`: это сторож нового риска (строк ступени кейсов до правки не было), а не повтор дефекта |
| Y6 до правки | `vitest run src/pages/__tests__/ops.test.tsx -t Y6` | failed: `Unable to find an element with the text: данных не хватило` — экран не знал слов исходов, а 41 «не положен по группе» шёл строками |
| После правки | те же тесты, `tests/test_cases_pack.py`, `tests/test_api_runs.py`, `tests/test_budget_spend.py` | passed |
| Бэкенд целиком | `pytest -q` на своей копии дев-базы (`cases_casestage_tests`) | 725 passed, 3 skipped — на ветке #27 после вливания в неё `main` с #26; до вливания — 722 passed. На ветке #27 без этой правки — 714 passed, 3 skipped (копия поставки #27) |
| Фронт целиком | `vitest run` | 202 passed (17 файлов) |
| Типы и стиль | `mypy src/ahrefs_cases`, `ruff check`, `ruff format --check`, `tsc --noEmit`, `eslint --max-warnings 0 src`, `prettier --check src` | чисто |
| Миграция: цикл на копии с данными | копия дев-базы `cases_casestage_migrate` (578 строк `run_items`): `alembic upgrade head` → `downgrade -1` → `upgrade head` | все три шага зелёные; `enum_range(NULL::run_item_outcome)` после первого подъёма — `{OK,…,SKIPPED_ABORTED,CASE_NOT_ELIGIBLE,CASE_INSUFFICIENT_DATA,CASE_NO_VERDICT,CASE_VERDICT_MISMATCH,CASE_BLOCKED}` — **имена** членов (урок L12); после отката значения остаются (у Postgres нет `DROP VALUE`, откат — осознанный no-op), повторный подъём проходит на `IF NOT EXISTS`; `'CASE_NOT_ELIGIBLE'::run_item_outcome` принимается, `'case_not_eligible'` — `invalid input value`; строк `run_items` 578 до и после |
| Миграция: цикл с нуля | `MIGRATION_CYCLE_TEST=1 pytest tests/test_migrations.py` на пустой базе `cases_casestage_cycle` | passed: `upgrade head` → `downgrade base` (типов ENUM не осталось) → `upgrade head`; голова `a8b9c0d1e2f3`, пять новых имён на месте |
| Миграция на копии перед исполнением | `alembic upgrade head` на `cases_casestage_check` | `f7a8b9c0d1e2 -> a8b9c0d1e2f3`; `/api/health` — `migration: a8b9c0d1e2f3` |
| Фазовый гейт | `python3 scripts/delivery_check.py --diff-base origin/main` | 0 ошибок; до слияния #27 — с `--diff-base bugfix/two-campaigns-two-cases`: поставка была отведена от его ветки |
| CI на ветке поставки | GitHub Actions, PR #29, коммит 4b98af8 | delivery, gates, tests — pass (726 passed, 2 skipped): https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36061022773 |
| Исполнение (Y10) | ниже — «Исполнение рисковых путей» | журнал и экран сошлись со сборкой; до правки — «0 из 75», судеб нет |

## Исполнение рисковых путей

`web/src/pages/runs/` — раскрытие прогона сборки кейсов со всеми исходами в
пропорциях живого ответа. Исполнено кнопкой через API: `serve_api.py` (код
worktree) с `QUEUE_BACKEND=redis` и воркер RQ `SimpleWorker` на своей очереди
`casestage-check` (Redis db 7), копия дев-базы `cases_casestage_check` (75
проектов), провайдер `fixture`, ключа нет, каталог выгрузки — свой в
scratchpad; `journal_probe.py` жмёт `POST /api/runs/cases` и читает
`GET /api/runs/{id}` и `GET /api/alerts`; экран — боевая сборка фронта
(`vite build`) под `vite preview` с прокси `/api`, headless Chrome 154 по CDP
(`node drive_journal.cjs <base> <run> <png>`), нажатие «?» у прогона. До правки
— код ветки #27 (`fa7da7c`), после — ветки; перед прогоном «после» копия
пересоздана из того же дампа и поднята миграцией. at=2026-09-25

| Состояние копии | До правки | После правки |
|---|---|---|
| А: вердикты по живым рядам, сборка читает фикстурные (прогон 1838) | журнал «0 из 75, пропущено 75», судеб 0; оповещение «готов кейс wineverygame.com — Кейс v43.pdf» при пустом каталоге выгрузки | «0 из 75, пропущено 75» — пачки нет, и это правда; судеб 75: 12 «вердикт не про эти данные» с советом «переклассифицируйте по рядам «live», по которым вынесен вердикт (`classify --source live`), а не по текущему режиму», 21 «данных не хватило», 42 «не положен по группе»; повода о пачке нет |
| Б: переклассифицировано по фикстурным рядам (прогон 1839) | в ZIP 61 кейс, а журнал — «0 из 75, пропущено 75», судеб 0; оповещение «готов кейс zooplus.de — Кейс v11.pdf» | «61 из 75, пропущено 14»; судеб 75: `ok` 61 («кейс собран: nordvpn.com — Кейс v11.pdf», «… v11 (2).pdf» — две кампании порознь), 6 «не отдан: контент-запрет», 4 «данных не хватило», 4 «не положен по группе»; оповещение «готова пачка кейсов «кейсы-2026-09-24.zip»: кейсов внутри — 61 — проверьте перед публикацией»; в ZIP 61 PDF |
| Экран, прогон 1839 | «0 из 75 · пропущено 75 ?», раскрытие — «записей по доменам нет: прогон не дошёл до сбора» | «61 из 75 · пропущено 14 ?», раскрытие — 10 строк (4 «данных не хватило», 6 «не отдан: контент-запрет») с причинами, строки «без замечаний собрано: 61» и «не положен по группе: 4» |
| Экран, прогон 1838 | то же «записей по доменам нет» | 33 строки (12 «вердикт не про эти данные» с советом в две строки, 21 «данных не хватило»), строка «не положен по группе: 42» |
| Лог воркера | сводка — печатью в поток воркера, в журнал не уходила | `cases_packed … кейс собран: 67 … архив …` — 67 собранных минус 6 запрещённых = 61 в журнале |
| Удалена кампания 13039, чей кейс в пачке | — | повод `cases_pack_blocked`, `warning`: «пачка кейсов «кейсы-2026-09-24.zip» не отдаётся: в пачке кейс удалённого проекта — пересоберите кейсы, и архив соберётся без него» |

Снимки экрана просмотрены глазами: строки раскрытия не выходят из таблицы,
длинный совет переносится в две строки в своей колонке, числа «собрано» и «не
положен по группе» стоят под таблицей.

После проверки: копии `cases_casestage_check`, `cases_casestage_tests`,
`cases_casestage_migrate`, `cases_casestage_cycle` и дамп в контейнере удалены,
каталоги выгрузки и сборки фронта в scratchpad стёрты; API, воркер RQ,
`vite preview` и Chrome остановлены.

## Ревью рисковых мест

**Деньги.** Единственный путь units, который задевает поставка, —
`cache.empty_since`: память о пустом домене теперь пропускает строки с исходом
из `CASE_OUTCOMES` (`RunItem.outcome.not_in(CASE_OUTCOMES)`). Без этого
судьба «вердикта этой версии нет» или «данных не хватило», которую сборка
кейсов пишет пустому домену, рвала бы цепочку «нет данных» подряд, и
следующий сбор покупал бы пустоту заново — от 50 units за домен после каждой
сборки. Y5 держит это деньгами: после сборки кейсов `collect_all` берёт
пустоту из памяти (`REMEMBERED_EMPTY`), а не покупает. `ok` собранного кейса
в подсчёте остаётся — его собирают только проекту с данными. Ступень кейсов
Ahrefs не спрашивает.

**Транзакция БД.** `_pack` коммитит `start_run` отдельно (время начала видно
сразу), потом одной транзакцией: `pack_built` (строки `cases` и
`case_artifacts`), `add_item` на каждую судьбу, `run.projects_total`,
`finish_run` (итоги по строкам, статус) и один `session.commit()`. Упало
посреди — откатываются и кейсы, и судьбы, а `_run_guarded` закрывает прогон
`failed` с первопричиной; `_finish(only_if_open=True)` после успеха `done` не
переписывает. PDF и архив пишутся на диск до коммита — как и раньше: файл без
строки — мусор, который пересобирается, строка без файла невозможна.

**Безопасность.** Слова `password`, `access_token`, `Bearer`, `jwt_secret`
в диффе — из теста `test_cases_journal.py`: своя учётка
`journal@test.local`, секрет подписи подменён `monkeypatch`. Оповещения
по-прежнему за `require_right("read")`; новое в них — чтение каталога
выгрузки (`newest_pack`, `cases_inside`) и `holds_deleted_case`, то есть то
же, что отдаёт `GET /api/cases/pack` под тем же правом.

**Новые модули.** Миграция `a8b9c0d1e2f3`: только `ALTER TYPE … ADD VALUE IF
NOT EXISTS` в `autocommit_block` (иначе Postgres не даёт добавить значение
внутри транзакции), downgrade — no-op с причиной, как у `SKIPPED_ABORTED`.
`tests/test_cases_journal.py`: свои шесть проектов, своя версия порогов
(`isolated_ruleset`), уборка `delete_owned`; проекты стенда получают в сборке
теста «вердикта этой версии нет» и в пачку не попадают.

**Исход, которого нет в пачке.** `case_fates` берёт судьбу собранного кейса
из `Packed.packed` по `project_id`, иначе из `skipped` (`blocked[pid]`):
третьего не бывает — `pack` даёт каждому входу ровно один исход, а в пачку
уходят только собранные с вердиктом. Пустая пачка (`EmptyArchiveError`) несёт
запрещённые кейсы с собой (`exc.skipped`), и журнал называет их и тогда,
когда архива нет.

**Размер.** `cases_inside` читает PDF архива в память — как и
`packed_checksums`, которую оповещение зовёт тут же через
`holds_deleted_case`; пачка на 61 кейс — единицы мегабайт.

## Чего проверка НЕ доказывает

- **Прод.** На проде `live`; проверка — на копии дев-базы с провайдером
  `fixture`. Это `observe_signal`.
- **Совет при разных рядах.** Если вердикт вынесен по одним рядам, а сборка
  читает другие, совет «переклассифицируйте по рядам вердикта» кейс не
  соберёт — сборка читает ряды режима провайдера. Совет выбран тот, что не
  переписывает вердикты ни в каком режиме; что делать дальше — решение
  владельца (открытый вопрос спеки).
- **Прошлые прогоны сборки кейсов.** Строки журнала пишутся с этой правки;
  прогоны до неё так и останутся «0 из N» без судеб.

## Spec coverage gaps

- Нет: Y1–Y9 — тесты, Y10 — исполнение выше.

## Verdict
- [x] READY FOR HANDOFF — ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **34**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
Y4	assert "`classify --source live`" in advice["other-rows.example"]
Y4	assert "--source fixture" not in advice["other-rows.example"]
Y4	assert "`classify --source fixture`" in advice["moved.example"]
Y4	assert {item.domain: item.project_id for item in report.attempts} == {
Y1	assert card["status"] == "done"
Y1	assert card["projects_ok"] == 1, "собран один кейс — journal-good.example"
Y1	assert card["projects_total"] == _projects_in_base(writer)
Y1	assert card["projects_skipped"] == card["projects_total"] - 1
Y1	assert {domain: fate["outcome"] for domain, fate in _mine(card).items()} == {
Y2	assert reasons[GOOD] == f"кейс собран: {GOOD} — Кейс v1.pdf"
Y2	assert "«плохой»" in reasons[POOR] and "хорошим и средним" in reasons[POOR]
Y2	assert "«данных не хватает»" in reasons[THIN] and "карточке проекта" in reasons[THIN]
Y2	assert "контент-запрет: гео: «BY»" in reasons[BLOCKED]
Y2	assert f"«{RULESET}»" in reasons[NEW]
Y3	assert "вердикт вынесен по рядам «live», а показаны «fixture»" in reason
Y3	assert "переклассифицируйте по рядам «live»" in reason
Y3	assert "`classify --source live`" in reason
Y3	assert "--source fixture" not in reason
Y7	assert alerts == [
Y8	assert _cases_alerts(client, headers) == []
Y9	assert alerts == [
Y5	assert checked is not None, "два пустых ответа подряд включают память"
Y5	assert await empty_since(db_session, project_id) == checked
Y5	assert last.outcome is RunItemOutcome.OK
Y5	assert last.reason.startswith(REMEMBERED_EMPTY), "пустота взята из памяти, а не куплена"
Y6	expect(await screen.findByText('a-thin.example')).toBeInTheDocument();
Y6	expect(screen.getAllByText('данных не хватило')).toHaveLength(2);
Y6	expect(screen.getByText('вердикт не про эти данные')).toBeInTheDocument();
Y6	expect(screen.getByText(/переклассифицируйте по рядам «live»/)).toBeInTheDocument();
Y6	expect(screen.getByText('не отдан: контент-запрет')).toBeInTheDocument();
Y6	expect(document.querySelectorAll('tr[data-fate]')).toHaveLength(4);
Y6	expect(screen.getByText('без замечаний собрано: 10')).toBeInTheDocument();
Y6	expect(screen.getByText('не положен по группе: 41')).toBeInTheDocument();
Y6	expect(screen.queryByText('c0.example')).not.toBeInTheDocument();
```

✅ **Каждое утверждение ведёт к примеру спеки** (Y1 Y2 Y3 Y4 Y5 Y6 Y7 Y8 Y9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 16 code (+11 process docs) / +816/-57 (net +759) |
| commits | 8 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_cases_journal.py (новый оракул) |
| implement_retries | 0 — mypy, ruff, tsc, eslint и тесты зелёные с первого прогона правки; рабочие правки однажды пропали из дерева посреди работы (чужой запуск pre-commit в этом worktree в 00:00 спрятал неподготовленные изменения и не вернул) и восстановлены из его патча `~/.cache/pre-commit/patch…` — после этого правки коммитились сразу |
| verify_fails_before_green | 0 — сьют, фронт и фазовый гейт зелёные с первого прогона после правки; перенос на свежий `main` дал один конфликт (`knowledge/log.md`, обе записи оставлены) и зелёный повтор сьюта (725 passed) |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.

