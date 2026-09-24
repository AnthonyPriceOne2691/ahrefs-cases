# Active delivery status

- **slug:** usage-counts-live-units-only
- **stack:** delivery@1.92, cqg@2.33, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_api_usage.py::test_fixture_run_is_not_spent
- **diagnosis:** active/diagnosis.md
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-24 by=human:anthony («поправь расхождение»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит, правка живёт в ответе API и на экране
- **ci-oracles:** tooling
- **worktree:** .claude/worktrees/agent-a6d06058dc5eda5c5 (ветка `bugfix/usage-counts-live-units-only` от `origin/main`; основной клон занят живым прогоном на проде)
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/usage/ reason=числа экрана — суммы по настоящей базе, где смешаны оба режима; тесты строят журнал сами, и сходится ли экран с SQL на настоящей смеси, видно только исполнением
- **irreversible_surfaces:** none reason=автомерж в репозитории выключен, каждый PR сливает человек; выкатка в прод — ручная, по `docs/PROD.md`; `live` включает только владелец; проверка идёт на копии дев-базы, которая удаляется после проверки
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

«Потрачено» и «стоимость запуска на сто доменов» на экране расхода считались
роутером напрямую по всему журналу — вместе с условными units fixture-прогонов,
которые вычет из остатка (`budget.live_spend_since`) по правилу L116 не берёт.
Правило переезжает в одно место (`collect/budget.py`), его зовут все пути, а
условные units экран называет отдельной строкой.
