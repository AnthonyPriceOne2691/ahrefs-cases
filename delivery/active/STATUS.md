# Active delivery status

- **slug:** tests-own-rows
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_cleanup_scope.py::test_tests_delete_only_their_own_rows
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («Брать её сейчас»)
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** tests/owned_rows.py reason=свойство проверяется прогоном: контрольные строки в дев-базе обязаны пережить полный `pytest`
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** человек, собравший данные руками, находит их на месте после чужого прогона тестов
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Четыре модуля тестов в уборке за собой выполняют `delete(Model)` **без фильтра**:
`MetricPoint`, `Verdict`, `Run`, `UnitsLedger`, `Case`, `CaseArtifact`. То есть
любой `pytest` стирает из дев-базы всё, а не своё.

Нашлось показом экрана: карточка сказала «не классифицирован» про проект,
который часом раньше был «хорошим». Данные пришлось собирать заново дважды.
На общей дев-базе агентства это будет уносить чужую работу молча.
