# Active delivery status

- **slug:** web-intake
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («Приём доменов + экран загрузки»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** no reason=файл уходит телом запроса, всё остальное уже стоит
- **runtime_paths:** web/src/pages/IntakePage.tsx reason=блокировка запуска при нехватке квоты проверяется исполнением: кнопка обязана быть недоступна, а причина — названа
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** человек из PR-отдела загружает список и запускает прогон, не открывая консоль; отказ по квоте виден до нажатия, а не после
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Первый экран, ради которого сервис вообще существует для человека: загрузить
список, увидеть цену и запустить прогон. До него всё это существовало только по
HTTP, а значит требовало инженера.

Главное свойство — **блокировка до траты, а не после**. ТЗ требует показать
смету и не дать запустить прогон, когда квоты не хватает; цена ошибки здесь —
units заказчика, а не неудобство.
