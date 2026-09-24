# Active delivery status

- **slug:** cases-stage-journal
- **stack:** delivery@1.92, cqg@2.33, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_cases_journal.py::test_cases_run_counts_and_names_every_project
- **diagnosis:** active/diagnosis.md
- **phase:** tasks
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-24 by=human:anthony (одобрен пункт «Журнал сборки кейсов»; из задания: «Нужно: счётчики прогона ступени кейсов по фактической сборке и судьбы по проектам с причиной словами — «собран», «не положен по группе», «данных не хватило», «вердикт не про эти данные» (последнее — с советом, который не вредит проду: переклассификация по тем рядам, по которым вынесен вердикт, а не по текущему провайдеру)»; «оповещение «готов кейс <файл> — проверьте перед публикацией» … пусть говорит про пачку и число кейсов в ней»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефакты сборки (ZIP, PDF) не меняются: правка — журнал прогона, оповещение и экран журнала
- **ci-oracles:** tooling
- **worktree:** .claude/worktrees/agent-afac83d6310fad99c (ветка `bugfix/cases-stage-journal` от `bugfix/two-campaigns-two-cases`, PR #27: судьбы собранных кейсов опираются на его исходы `pack` по номеру проекта; фазовый гейт и предохранители гоняются с `--diff-base bugfix/two-campaigns-two-cases`, пока #27 не слит)
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/runs/ reason=что видно в раскрытии прогона сборки кейсов, решает рендер живого ответа со всеми исходами в пропорциях прода; тест видит то, что ему подложили (L214)
- **irreversible_surfaces:** none reason=автомерж выключен, каждый PR сливает человек; миграция (`ADD VALUE`, без переписывания строк) доедет до прода только выкладкой владельца по `docs/PROD.md` с бэкапом перед ней; проверка — на копиях дев-базы, которые удаляются
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** —
- **observe_until:** —
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Журнал прогона сборки кейсов писал «собрано 0, пропущено N» при собранной пачке
и не показывал ни одной судьбы, хотя сводка сборки была в логе воркера (L130).
Задача получает от сборки исходы по проектам, пишет их строками журнала и
закрывает прогон по ним; совет у «вердикт не про эти данные» называет ряды
вердикта; оповещение говорит про пачку и число кейсов в ней.
