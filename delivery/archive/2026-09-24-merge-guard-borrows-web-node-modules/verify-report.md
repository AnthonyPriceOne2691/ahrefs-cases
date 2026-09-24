# Verify report: merge-guard-borrows-web-node-modules

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| G2: слитое дерево получает `node_modules` каждого фронта и `.venv` | `pytest tests/test_merge_guard_environment.py` | passed; **падал до правки** — «одолжено окружение: .venv», заглушка: «нет окружения: web/node_modules», «МЕРЖ ЗАБЛОКИРОВАН — красные гейты: pre-commit (all files)» |
| Тест ловит порчу, а не только правку | три порчи `scripts/merge_guard.sh`, откатанные после прогона | список без `web` → «нет окружения»; гейт в клоне вместо временного дерева → «pre-commit гонялся в клоне»; гейт пропущен → «гейт pre-commit не запускался» — 3 из 3 красные |
| G1: гейт мержа без `MERGE_GUARD_BORROW` | `DRY_RUN=1 bash scripts/merge_guard.sh bugfix/merge-guard-borrows-web-node-modules main` | «одолжено окружение: web/node_modules», `pre-commit (all files)` OK, baseline ratchet OK, delivery gate OK, canon sync OK; `ci status` красный до первого прогона CI — ожидаемо |
| G3: канонное поведение | дифф `scripts/merge_guard.sh` | одно слово в умолчании плюс комментарий; `backend/.venv frontend/node_modules .venv node_modules` и `${MERGE_GUARD_BORROW:-…}` не тронуты |
| G4: адаптация объявлена | `scripts/lint/adapted.json` | запись `merge_guard.sh` с `reason`/`changed`/`kind: adaptation` |
| Форма кода | `pre-commit run --all-files` | 29 хуков, упавших 0 |
| Фазовый гейт | `python3 scripts/delivery_check.py --diff-base origin/main` | 0 ошибок |
| Бэкенд целиком | `pytest -q` на дев-базе | 663 passed, 3 skipped (медленные, без стека) |
| CI на ветке поставки | GitHub Actions, PR #19 | delivery, gates, tests — pass: https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36011872616 |

## Исполнение рисковых путей

`scripts/merge_guard.sh` — гейт мержа с настоящими хуками судится только
исполнением: тест ставит заглушку вместо pre-commit. Исполнено прогоном
`DRY_RUN=1` из worktree поставки, ветка поверх `origin/main` 8b2af55,
at=2026-09-24.

Чтобы увидеть, что напечатали гейты во временном дереве (на успехе merge_guard
вывод гейта прячет), pre-commit подменён обёрткой с `--verbose` и журналом;
каталог запуска в журнале — временное дерево
`…/T/tmp.xwk5W3DmAl/merge-check`, а не клон. Одна и та же ветка, одна и та же
цель; «до» — скрипт из `origin/main`, «после» — из ветки.

| Гейт во временном дереве | До правки | После правки |
|---|---|---|
| Одолжено окружение | `.venv` | `web/node_modules`, `.venv` |
| ESLint (хук) | **Failed** — `Oops! Something went wrong! :( ESLint: 10.11.0` | Passed, 1.92 с |
| Prettier (хук) | **Failed** — `npx canceled due to missing packages … ["prettier@3.9.9"]` | Passed, 0.76 с |
| eslint-ратчет предупреждений | зелёный, **пропущен**: «eslint не найден» | OK — просмотрено 101 файл |
| jscpd | зелёный, **пропущен**: «jscpd не найден» | OK (python + ts) — 204 файла |
| слои | половин просужено **1** (ts: «depcruise не найден») | половин просужено 2 (ts: 104 модуля) |
| сложность | только python, 120 файлов (ts: «eslint не найден») | python + ts — 224 файла |

То есть до правки гейт мержа ошибался в обе стороны сразу: два хука красные не
по коду и четыре гейта TS зелёные, не просудив ни одного файла фронта.

## Ревью рисковых мест

**Цепочка гейтов (`merge_guard`).** Правка меняет только умолчание
`BORROW_DIRS`: какой каталог одалживается во временное дерево. Порядок и состав
гейтов, `run_gate`, `gate_or_skip`, проверка грязного дерева и сам мерж не
тронуты. Одалживается только существующий каталог
(`[[ -e "$REPO_ROOT/$dev" ]]`), поэтому на клоне без `web/node_modules`
поведение прежнее: хуки eslint и prettier красные по окружению, ратчеты TS
пропускаются, — правка не превращает отсутствие инструмента в зелёное.
Переопределение `MERGE_GUARD_BORROW` по-прежнему заменяет список целиком: тот,
кто его задаёт, берёт `web/node_modules` на себя.

**Новый модуль (`test_merge_guard_environment`).** Тест исполняет настоящий
скрипт на одноразовом репозитории в `tmp_path`; окружение процесса очищено от
`GIT_*` и `MERGE_GUARD_*`, глобальный конфиг git выключен
(`GIT_CONFIG_GLOBAL=/dev/null`) — тест, запущенный из git-хука, не дотянется до
индекса настоящего репозитория, а `MERGE_GUARD_BORROW` разработчика не подменит
проверяемое умолчание. Сеть и база не нужны.

**Транзакция БД (`commit`).** Слово из `_git(…, "commit", …)` — коммит в
одноразовом репозитории полигона, не транзакция базы: риска нет, потому что тест
базы не открывает вовсе.

## Окружение проверки

Worktree поставки получил окружение из основного клона. Симлинком на каталог
этого сделать нельзя: `.gitignore` проекта пишет `node_modules/` и `.venv/` с
косой чертой, а такой шаблон совпадает только с каталогом — симлинк git видит
файлом, дерево становится грязным, и merge_guard отказывается работать
(«рабочее дерево грязное»). Поэтому `web/node_modules` и `.venv` здесь —
настоящие каталоги из симлинков на содержимое клона; `git status` чистый, npx
находит `eslint` 9.39.5.

## Что осталось за рамками

**Второй слой того же класса — в каноне, не в проекте.** Хуки фронта зовут
инструмент через `npx --no-install`: без локальной установки eslint молча
берётся из кэша npx (любой версии, что там окажется), а prettier отказывает.
Ратчеты TS без инструмента выходят 0 с предупреждением — оффлайн-профиль
объявлен законным в `cqg@1.23`. После этой поставки во временном дереве гейта
мержа инструмент есть, и обе ветки не срабатывают; но на машине без
`npm ci` в `web/` тот же хук снова возьмёт чужой eslint. Лечится в каноне:
хук, не нашедший `node_modules/.bin/eslint`, падает со словами «npm ci в web/»,
а не идёт в кэш; адресат — владелец канона.

**Умолчание всё ещё знает раскладку.** Канон мог бы брать каталоги из
`LINT_FE_DIR` или из отслеживаемых `package.json`, как делает тест; в проекте
это была бы вторая копия логики поверх канонного скрипта. Здесь дрейф ловит
тест.

## Verdict
- [x] READY FOR HANDOFF — подписал human:anthony at=2026-09-24 («сливай» — ответ на предложение слить #19)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 3 code (+5 process docs) / +180/-1 (net +179) |
| commits | 1 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — scripts/lint/adapted.json, tests/test_merge_guard_environment.py (новый оракул) |
| implement_retries | 0 — правка зелёная с первого прогона теста; одна попытка окружения: симлинки на каталоги клона сделали worktree грязным (`.gitignore` с косой чертой симлинк не прячет), заменены каталогами из симлинков |
| verify_fails_before_green | 0 по оракулам поставки; `delivery_check` дважды предупредил по форме — решение без цены (число словом) и не упомянутый урок L57; DRY_RUN красный только по `ci status` до первого прогона CI |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
