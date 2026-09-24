# Active delivery status

- **slug:** project-deletion-api
- **stack:** delivery@1.92, cqg@2.33, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** tests/test_api_projects_delete.py::test_journal_keeps_each_deleted_project_apart
- **diagnosis:** n/a reason=не дефект, а новая возможность по решению владельца; попутный дефект свёртки судеб (все удалённые проекты прогона сливались в одну судьбу) виден в коде без поиска — ключ `_fold_by_project` по `project_id`, который удаление обнуляет
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-24 by=human:anthony («введи функционал удаления проектов…»; на развилки: «Новое право», «Удалять вместе», «Не отдавать до пересборки»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит: поставка удаляет строки и файлы, а не собирает их
- **ci-oracles:** tooling
- **worktree:** .claude/worktrees/agent-a3b5625ef78b60385 reason=параллельно в соседнем worktree идёт поставка `bugfix/usage-counts-live-units-only`; ветка `feature/project-deletion-api` от свежего origin/main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/export/removal.py reason=удаление на живой базе и файлы на диске: каскад по настоящим строкам стенда, общий файл двух кейсов и путь артефакта относительно рабочего каталога проверяются исполнением на копии дев-базы, а не тестом с временным каталогом
- **irreversible_surfaces:** none reason=агент удаляет только на копии дев-базы `cases_delete_check` и в каталоге выгрузки своего scratchpad; прод и дев-стенд не трогаются, слияние PR и выкатку делает человек
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на проде после первого удаления: D1 (строк проекта ноль, PDF ушёл) и D2 (строка журнала на месте с доменом, расход не изменился); лог `project_deleted` с числами по таблицам
- **observe_until:** 2026-10-08
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Удаления проекта не было вовсе. Владелец попросил его 24.09.2026 и уточнил на
развилках: удаление жёсткое, каскадом — оплаченные ряды уходят вместе с
проектом («Удалять вместе»: повторная загрузка купит их заново); право новое,
«удалять проекты», у групп engineer и admin, лично выдаётся и отбирается
(«Новое право»); пачка ZIP, в которую вошёл кейс удалённого проекта, не
отдаётся до пересборки («Не отдавать до пересборки»).

Это первая из двух поставок: API и бэкенд. Экран — кнопка на карточке,
предпросмотр «что уйдёт», подпись права, «(проект удалён)» в судьбах прогона и
предупреждение на карточке пачки — вторая, после слияния этой.
