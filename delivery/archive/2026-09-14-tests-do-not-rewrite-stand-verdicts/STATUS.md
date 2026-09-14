# Active delivery status

- **slug:** tests-do-not-rewrite-stand-verdicts
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/conftest.py::stand_verdicts_survive_the_suite
- **diagnosis:** n/a reason=причина найдена замером и записана как Z12: тест пересчитывает действующую версию порогов, то есть чужие вердикты
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026 — «давай z12 и так далее»)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («давай z12 и так далее»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=правка тестов и их сторожа, рантайм сервиса не затронут
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** после полного прогона тестов вердикты стенда остаются теми же, что были до него
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Z12. `tests/test_api_thresholds.py::test_recalc_runs_without_touching_ahrefs`
делает `POST /api/rulesets/{действующая}/recalc`, а пересчёт идёт по **всем
проектам базы** — то есть и по сорока проектам стенда, с источником режима API
(`fixture`), и коммитит. Правило уборки «убираем свои строки» здесь не
срабатывает: тест не создавал эти строки, он их перезаписал.

Замерено 14.09.2026: до прогона 40 вердиктов `LIVE`, после — 40 `FIXTURE`.
Практическое следствие — после любого `pytest` калибровка, посчитанная по живым
рядам, заменяется фикстурной, и её приходится делать заново.

Дефекту столько же лет, сколько тесту, но **увидеть** его стало можно только
14.09: до того вердикт не хранил источник, и подмена выглядела как те же самые
числа. Поправка к поставке `verdict-remembers-its-source`: поле, заведённое
ради кейсов, сразу же показало чужую поломку.
