# Active delivery status

- **slug:** tests-return-the-stand
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_classify_recalc.py::test_two_active_versions_are_impossible
- **diagnosis:** n/a reason=не дефект продукта: тесты меняют чужую строку на общем стенде
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («всё должно работать безукоризненно»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/classify/recalc.py reason=порядок записи при переключении версии проверяется только на базе с уже активной версией
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** после прогона тестов действующая версия порогов на стенде та же, что была до него; двух активных версий не существует
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Тесты и дев-стенд делят одну базу — это осознанное решение Ф1, и тесты
убирают за собой **свои строки** (`tests/owned_rows`). Но `test_api_thresholds`
делает больше: он активирует версию порогов, то есть меняет флаг у **чужой**
строки, а в уборке удаляет только свою.

Сегодня это стоило часа разбирательства: на стенде была активирована версия
`0.1.0-проверка`, после прогона тестов активной оказалась `0.0.0-default`, и
пересчёт «по действующей версии» считал не то, что ожидалось.

Пока чинили уборку, вскрылось большее: на стенде оказались **две** активные
версии порогов сразу. Инвариант «активная одна» держался тем, что `activate`
гасит остальные, — то есть дисциплиной вызывающих. `active_ruleset` при двух
активных молча берёт новейшую по id, и вердикты считаются порогами, которых
никто не утверждал.
