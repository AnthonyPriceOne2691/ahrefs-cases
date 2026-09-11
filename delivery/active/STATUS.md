# Active delivery status

- **slug:** tests-need-db
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** chore
- **repro_test:** n/a reason=меняется поведение самого прогона тестов; проверяется исполнением с погашенной базой
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай» — сделать отсутствие базы локальной ошибкой)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** tests/conftest.py reason=поведение прогона без базы проверяется только запуском с погашенной базой
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** прогон без базы останавливается первой же строкой с командой, которой её поднять, а не заканчивается «зелёным» с сотней пропусков
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Без поднятой базы `pytest` печатает «253 passed, 154 skipped» и возвращает ноль.
Формально честно: пропуск и успех в выводе различаются. Практически — это
зелёный прогон, доказавший чуть больше трети, и увидеть это можно только
вчитавшись в число.

Найдено при переносе сервиса в контейнеры: погасил дев-стек, прогнал тесты,
получил зелёно.
