# Active delivery status

- **slug:** ahrefs-live-shapes
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_collect_endpoints_live.py (формы ответов и цены из замеров живым ключом)
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-12 by=human:anthony (снял запрет на живой Ahrefs и просил прогнать все нужные сценарии)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/collect/endpoints.py reason=формы ответов и цены проверяются только живым ключом; на фикстурах обе стороны согласованы по нашей же догадке
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** смета совпадает с заголовком `x-api-units-cost-total` на живых запросах; DR и объём поиска разбираются, а не падают
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Живой ключ 12.09.2026 показал, что две спеки из восьми описывают ответ неверно,
а модель цены угадана: она считает «10 за любое поле», тогда как у каждого поля
цена своя. Первое ломает сбор молча (ошибка формы читается как «нет истории»),
второе врёт в смете — в обе стороны.
