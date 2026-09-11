# Active delivery status

- **slug:** web-runs-usage
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («продолжай» — следующие экраны Ф6: журнал прогонов и расход units с алертами)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/RunsPage.tsx reason=идущий прогон проверяется исполнением: журнал обязан обновляться сам, пока прогон не закончится
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** оператор видит, что прогон идёт и чем закончился, не заглядывая в логи; остаток units и поводы для тревоги видны до того, как кто-то нажмёт «запустить»
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Прогон запускается с экрана загрузки и уходит в фон на часы. Посмотреть, что с
ним, можно только курлом: «Прогоны» и «Расход units» — заглушки.

Это операционная пара экранов: один отвечает «что происходит и чем кончилось»,
второй — «сколько денег осталось и на что смотреть». ТЗ просит мониторинг units
прямо: алерты при превышении и отчёт после каждого прогона.
