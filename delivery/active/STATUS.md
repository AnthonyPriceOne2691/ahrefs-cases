# Active delivery status

- **slug:** project-deletion-ui
- **stack:** delivery@1.92, cqg@2.33, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** web/src/pages/__tests__/card.test.tsx
- **diagnosis:** n/a reason=не дефект: экран к API удаления, заведённому поставкой project-deletion-api
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-24 by=human:anthony (через координатора: «Владелец одобрил вторую поставку удаления — экран»; состав — список из отчёта первой поставки: кнопка на карточке по праву из `/me` с предпросмотром из `GET …/deletion`, подпись права, «(проект удалён)» в судьбах прогона, предупреждение на карточке пачки)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит: экран показывает то, что отдаёт API
- **ci-oracles:** tooling
- **worktree:** .claude/worktrees/agent-a3b5625ef78b60385 reason=ветка `feature/project-deletion-ui` от `origin/feature/project-deletion-api` (#23 ещё не слит); после его слияния — перенос на `origin/main`
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/card/DeleteProject.tsx reason=удаление с подтверждением проходится кнопкой в браузере на боевой сборке и копии базы: jsdom не видит ни раскладки окна подтверждения, ни тем, ни того, что карточка после удаления не упирается в `404`
- **irreversible_surfaces:** none reason=удаление исполняется только на копии дев-базы в scratchpad; прод и дев-стенд не трогаются, слияние PR и выкатку делает человек
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на проде первое удаление кнопкой: PD2 (окно называет числа предпросмотра), PD4 (карточка сменяется итогом, список проектов без удалённого), PD7 («(проект удалён)» в раскрытии прогона)
- **observe_until:** 2026-10-08
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Вторая из двух поставок «удаление проектов» — экран к API первой (#23).
Человек с правом «удалять проекты» видит на карточке кнопку, а перед
удалением — что уйдёт и что останется, числами предпросмотра. Журнал прогонов
подписывает судьбу удалённого проекта, карточка пачки говорит, почему пачку
нельзя скачать, экран людей называет новое право словами.
