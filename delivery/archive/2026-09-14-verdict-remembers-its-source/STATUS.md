# Active delivery status

- **slug:** verdict-remembers-its-source
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_cases_builder.py::test_case_refuses_when_the_verdict_came_from_other_data
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026 после живой проверки на двух источниках)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony (Z10 объявлен главным открытым дефектом и назначен следующей поставкой)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** case-pdf reason=дефект виден именно в собранном PDF: таблица и график из разных миров
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=миграция добавляет поле; данные на стенде переклассифицируются бесплатно
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** сборка кейсов по калибровочному набору не выдаёт ни одного кейса, где таблица и график считаны из разных источников
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Вердикт не помнил, по каким рядам его вынесли. Кейс брал числа таблицы из
вердикта, а кривые — из рядов источника, названного вызывающим, и при живых и
фикстурных рядах одного проекта в одном PDF оказывались числа из разных миров:
`wickes.co.uk` 14.09.2026 — в таблице «35 394 → 60 101», на графике последняя
точка 1 058 129.

Это нарушение первого правила конституции: числа в кейсе сверяются с данными
программно. После поставки вердикт хранит источник, кейс отказывается
собираться при несовпадении, а числа точек сверяются с рядами — тем же кодом,
которым их считала классификация.
