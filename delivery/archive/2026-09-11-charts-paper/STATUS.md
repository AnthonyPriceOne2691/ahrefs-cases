# Active delivery status

- **slug:** charts-paper
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_cases_charts.py::test_chart_carries_its_own_paper
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай оптимальный вариант с подложкой»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** PDF пересобирается и сверяется глазами: бумага рисунка не должна спорить с бумагой листа
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/export/charts.py reason=читаемость проверяется глазами на обеих темах и на собранном PDF, а не утверждением в тесте
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** карточка читается в обеих темах без подкрутки браузера; кейс в PDF выглядит как прежде
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Рисунок кривых сделан для печати: чернила выбраны под белый лист, а заливка под
кривой **затухает в цвет полотна** (`SURFACE`). В PDF полотно белое, и всё
сходится. В вебе карточка бывает тёмной — и тогда у рисунка нет фона вовсе:
подписи значений (`#0b0b0b`) держатся только там, где под ними светлая заливка,
а само затухание читается белой дымкой на тёмном.

Найдено не тестом и не ревью, а тем, что браузер открылся в тёмной теме.
