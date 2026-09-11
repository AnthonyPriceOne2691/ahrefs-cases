# Active delivery status

- **slug:** thresholds-edit
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony (выбран вариант «править только то, что решает группу»: условия групп, пригодность, ограничитель; окна точек и веса счёта остаются на просмотр)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/thresholds/EditSection.tsx reason=активация меняет то, что видят все; путь «сохранил → посмотрел → применил» проверяется исполнением на стенде
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** заказчик правит цифру и видит последствия до применения; версия сохраняется отдельно от активации, и вердикты пересчитываются отдельной кнопкой
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

ТЗ требует: «правишь цифру — видишь „12 проектов сменят группу, 3 перейдут в
хорошие"». Смотреть уже можно, править — нет: версии заводятся только курлом.

Правятся те значения, что **решают группу**: условия «хорошего» и «среднего»,
пригодность, ограничитель. Окна точек А и Б и веса счёта остаются на просмотр —
они меняют смысл самих данных, а не границу (решение владельца 11.09.2026).
