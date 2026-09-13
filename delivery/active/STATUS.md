# Active delivery status

- **slug:** narrow-header-and-russian-statuses
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** web/src/app/__tests__/shell.test.tsx
- **diagnosis:** n/a reason=оба дефекта видны глазами и воспроизводятся разметкой
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («хвост Ф7 + два дефекта» — выбрано в списке работ до калибровки)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/app/Shell.tsx reason=шапка рассыпается только на узком экране, в jsdom ширины нет — проверяется глазами на 400 px
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** шапка на 400 px не наезжает на контент; ни один статус не показан латиницей
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Два незаблокированных дефекта, найденных живым показом интерфейса:

1. **Шапка на узком экране (400 px) рассыпается**: почта, группа и «Выйти» не
   влезают в строку, переносятся и наезжают на контент — высота `AppShell.Header`
   фиксирована (56 px), а содержимое стало выше.
2. **Статусы кейсов и прогонов показаны латиницей** (`BUILT`, `done`) посреди
   русского экрана. Словарь групп для этого уже есть (`pages/groups.ts`) — у
   статусов такого нет, и каждый экран печатает сырое значение.
