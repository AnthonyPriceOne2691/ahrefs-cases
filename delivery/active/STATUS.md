# Active delivery status

- **slug:** probe-measures-drift-not-equality
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_probe_next_day.py::test_noise_level_drift_in_a_closed_month_does_not_refute_the_rule
- **diagnosis:** n/a reason=причина видна из замера и записана как Z13
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
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
- **runtime_paths:** n/a reason=правка разведочного скрипта, рантайм сервиса не затронут
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** следующий замер H2 печатает величину дрейфа рядом с вердиктом
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Z13. `scripts/probe_next_day.py` сравнивал значения закрытых месяцев на точное
равенство и при любом расхождении печатал «H2 ОПРОВЕРГНУТА» с советом отодвинуть
границу кэша. Замер 14.09.2026 дал расхождение в **три визита из 4 550 157**
(0,00007 %) — вердикт формально верен, а совет по нему стоил бы 50 units за
домен при каждом обновлении.

`org_traffic` у Ahrefs — оценка; мы сами пишем это в сноске каждого кейса.
Оракул, судящий оценку на точное равенство, выносит приговор по шуму.
