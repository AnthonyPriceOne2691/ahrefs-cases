# Active delivery status

- **slug:** canonical-only-and-root-cause
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_run_failure_reason.py::test_recorded_reason_names_the_root_cause
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («погоняй остальную логику чтобы убедиться что она работает» — обе находки из этого прогона)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** scripts/run_collect.py, src/ahrefs_cases/workers/jobs.py reason=оба дефекта нашлись исполнением: один — при вводе домена человеком, второй — при падении задачи в воркере
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** домен, названный человеком, находится в базе; в журнале прогона видна первопричина падения, а не последняя ошибка
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Прогон всей логики живьём 13.09.2026 (приём → сбор → классификация → шаг 2 →
ступень кейса → кейсы → ZIP → очередь и воркер) прошёл целиком и нашёл два
дефекта — оба невидимы тестам, потому что тесты не набирают домен руками и не
падают дважды подряд.

1. **`--only` не находит домен, который человек только что загрузил.** Приём
   приводит домен к канону (`проверка-рост.example` → `xn----7sbfmzvfbjddnn.example`),
   а фильтр прогона сравнивает строку как введена. Ответ — «в базе нет
   проектов», хотя проект создан минуту назад тем же именем.
2. **Журнал прогона называет последнюю ошибку, а не первую.** Задача упала с
   `AttributeError: units_counter_lag_hours` (у воркера в памяти был старый
   модуль конфига), но в журнале и на экране прогонов осталось
   `MissingGreenlet: greenlet_spawn has not been called` — вторая ошибка,
   случившаяся при попытке записать первую. Человек читает следствие и чинит не то.
