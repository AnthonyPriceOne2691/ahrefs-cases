# Active delivery status

- **slug:** gates-judge-or-say-why-not
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_ci_gates_judge.py::test_suite_runner_job_has_a_database
- **diagnosis:** n/a reason=причина найдена прогоном CI и записана как Z18–Z20: сьют требует базы, а джоба `gates` идёт без неё
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-15 by=human:anthony («все три сразу», выбор маршрута «перенести в tests»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=правка оснастки CI и гейтов, рантайм сервиса не затронут
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** прогон CI на диффе с Python-кодом печатает число покрытия изменённых файлов, а не «изменённых prod-файлов нет»
- **observe_until:** 2026-09-29
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Три дефекта одного класса, вскрытые первым же прогоном CI на диффе с Python-кодом
(PR #2, 15.09.2026). Класс — «зелёный, потому что гейт не судил».

**Z18.** Шаг `Diff coverage` стоит в джобе `gates`, у которой нет Postgres, а
сьют с 11.09 (`tests/conftest.py::pytest_collection_modifyitems`) отказывается
стартовать без дев-базы: `pytest.exit(returncode=1)` на этапе сбора. Значит
`coverage.json` не появляется, и гейт красный **структурно** — на любом диффе,
где есть изменённый Python. Четыре дня этого не было видно, потому что каждый
пуш с 11.09 нёс дифф без Python: гейт печатал «изменённых prod-файлов нет» и
выходил нулём. Замер: прогон 34778321271 (13.09, зелёный) — строка
«diff-coverage: изменённых prod-файлов нет»; прогон 34940648465 (15.09, 25
изменённых файлов) — «coverage.json не найден».

**Z19.** `scripts/lint/check_diff_coverage.sh` отправляет весь вывод сьюта в
`>/dev/null 2>&1` и печатает «сьют не отработал?» — со знаком вопроса, потому
что сам не знает. pytest причину написал; её выбросили. Диагноз Z18 пришлось
доставать сравнением с логом позапрошлого прогона.

**Z20.** В том же прогоне мутационный гейт зелёный при 25 файлах в диффе:
«mutmut не может определить, что мутировать — гейт не судит». mutmut 3.x
гоняется из `src/` и читает там `[tool.mutmut] source_paths`; в корневом
`pyproject.toml` стоит ключ `paths_to_mutate` — имя из 2.x, мёртвое с 3.0.
Гейт, объявленный в контуре, не выносил вердикта ни разу.
