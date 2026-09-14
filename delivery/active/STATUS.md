# Active delivery status

- **slug:** screen-state-survives-reload
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** web/src/pages/__tests__/projects.test.tsx::фильтр и страница берутся из адреса при открытии
- **diagnosis:** n/a reason=причина понятна: состояние экранов жило только в памяти компонента
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («при обновлении любой страницы через f5 не должно сбрасываться состояние»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=состояние экрана, внешних вызовов нет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** F5 на отфильтрованном списке оставляет фильтр, страницу и раскрытого человека
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Состояние экранов жило только в памяти компонента: фильтр проектов, номер
страницы, тумблер версий у кейсов, раскрытый человек. F5 стирал всё, переход в
соседний раздел и обратно — тоже.

Теперь оно живёт в адресе страницы. Это даёт даром ещё две вещи: ссылку на
отфильтрованный список можно переслать, а пункт меню возвращает человека туда,
где он в разделе был.
