# Active delivery status

- **slug:** web-project-card
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («конечно, давай» — карточка проекта с вердиктом, таблицей А → Б и графиками)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит; рисунок проверен предыдущей поставкой
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/ProjectCardPage.tsx reason=карточка проверяется исполнением на настоящем вердикте: числа таблицы обязаны совпасть с числами кейса, а это видно только на данных
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** сотрудник объясняет группу проекта по экрану, не открывая PDF и не спрашивая инженера; числа карточки и кейса совпадают
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Таблица проектов показывает группу, но не отвечает на главный вопрос — **почему
именно эта**. Ответ записан в вердикте (условия, факты, пороги, точки А и Б) и
доступен только курлом: по адресу `/projects/:id` стоит заглушка.

Это же экран, на котором решают, брать ли проект в кейс. Значит он обязан
показывать то, что покажет кейс, — и теми же числами, иначе спор сотрудника с
PDF решается не в пользу сервиса.
