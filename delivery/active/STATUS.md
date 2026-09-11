# Active delivery status

- **slug:** users-manage
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («потом люди» — вторая половина того же экрана)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/users/ManageUser.tsx reason=пароль показывается один раз, и что человек успел его увидеть — вопрос к живому экрану, а не к тесту
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** администратор заводит человека и выдаёт права сам, без инженера и без консоли
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Смотреть людей уже можно, управлять — нет. Список сотрудников заказчик так и не
прислал, и ждать его незачем: администратор заводит людей сам (Ф5.5), а пароль
генерируется и показывается **один раз**.

Здесь же правка: группа, доступ ко входу и личные права — те самые, что
перекрывают группу в обе стороны.
