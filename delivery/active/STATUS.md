# Active delivery status

- **slug:** quota-counter-lag
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_collect_quota.py::test_spend_the_counter_has_not_seen_is_subtracted
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («сделать всё до калибровочных кейсов»; дефект найден живым прогоном того же дня и стоит перед боевым прогоном)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/collect/quota.py reason=разрыв виден только в живом режиме: у фикстурной квоты счётчика нет и отставать нечему
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** остаток, показанный человеку и проверенный preflight, — одно число, и в нём учтён расход, которого счётчик Ahrefs ещё не видит
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Живой замер 13.09.2026: счётчик `units_usage_api_key` реален, но **отстаёт** —
50 units, потраченные минутами раньше, в нём не видны. При этом резерв
(`budget.reserved_units`) учитывается только у прогонов в статусе
`queued`/`running`.

Значит между концом прогона и обновлением счётчика есть окно, в котором остаток
из API ещё не уменьшился, а резерв уже не удерживается. В этом окне `preflight`
пропустит следующий прогон по квоте, которой нет. На ключе в 2 000 000 units
это незаметно; на бюджете заказчика в 10 000 — это ровно тот отказ на середине
прогона, против которого весь модуль и написан.
