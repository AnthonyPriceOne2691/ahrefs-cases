# Active delivery status

- **slug:** journal-small-fixes
- **stack:** delivery@1.92, cqg@2.33, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_api_runs.py::test_fates_name_the_domain_as_people_write_it
- **diagnosis:** n/a reason=обе причины видны в коде без поиска: судьба отдаёт `raw_domain` каноном (`api/routers/runs.run_status`), правило 4а (`to_unicode`) зовёт только сборка кейса; `RunRow` не несёт режима прогона, хотя он лежит в `params_snapshot['provider']`
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-24 by=human:anthony (через координатора: «Начинай следующую поставку „мелочи журнала“ — владелец её одобрил»; состав: домен по-человечески в журнале прогонов одним правилом с кейсом, журнал называет режим прогона fixture/live)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит: правка живёт в ответе API и на экране
- **ci-oracles:** tooling
- **worktree:** .claude/worktrees/agent-a3b5625ef78b60385 reason=ветка `feature/journal-small-fixes` от свежего origin/main; параллельно другой агент правит сборку кейсов — `collect/run_journal.py` не трогается
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/runs/RunsTable.tsx reason=журнал на настоящих прогонах стенда проверяется исполнением: какие прогоны помечены условными и как читается колонка units, видно на живом рендере, а тест видит только подложенные строки
- **irreversible_surfaces:** none reason=правка читает журнал и не пишет ничего; проверка на копии дев-базы, слияние и выкатку делает человек
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на проде журнал прогонов: W4 (живые прогоны без пометки), W1 (кириллический домен в раскрытии — по-человечески)
- **observe_until:** 2026-10-08
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Две мелочи журнала прогонов, найденные на экране и в поставке про учёт units.
Раскрытие судеб пишет часть доменов каноном (`xn--mller-shop-9db.de`), хотя
кейс пишет их по-человечески (правило 4а); и журнал не называет режим прогона
— у fixture-прогона «смета → факт» выглядит как настоящий расход (открытый
вопрос Z38).
