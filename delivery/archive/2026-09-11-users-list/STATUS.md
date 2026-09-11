# Active delivery status

- **slug:** users-list
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («потом люди» — последний экран Ф6 по согласованному порядку)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/UsersPage.tsx reason=права людей видны только на настоящих учётках стенда; на фикстуре не отличить «как в группе» от «выдано лично»
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** администратор видит, кто заведён и что каждому можно — включая право, выданное лично поверх группы
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

`/users` — последняя заглушка Ф6. API людей готов целиком (список, заведение,
правка, перевыпуск пароля), но увидеть, кто заведён и что кому можно, из
интерфейса нельзя.

Эта половина отвечает на вопрос «кто есть и что ему можно»: список с группами,
активностью и — отдельно — правами, выданными **лично**. Заведение, правка и
перевыпуск пароля приедут следующей поставкой.

Заодно на бэке заводится справочник прав: без него экран держал бы вторую копию
таблицы прав, а копия расходится молча (урок L97).
