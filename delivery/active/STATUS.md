# Active delivery status

- **slug:** tables-and-forms-line-up
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** chore
- **repro_test:** web/src/pages/__tests__/cases.test.tsx::листает по двадцать строк
- **diagnosis:** n/a reason=не дефект логики: замечания по виду экранов, снятые владельцем со скриншотов
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony (пять замечаний со скриншотов)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/styles/glass.css reason=яркая полоса за шапкой панели видна только в браузере на длинной странице: в jsdom фона нет вовсе
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на экранах проектов и кейсов по двадцать строк, колонки выровнены, поля формы одной ширины
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Пять замечаний владельца, снятых со скриншотов работающего сервиса:

1. поля «Файл со списком» и «Ссылка на Google Sheet» разной ширины;
2. за шапкой «Сметы прогона» видна светлая полоса во всю ширину панели;
3. поле «Поиск по домену» растянуто на всю ширину экрана;
4. таблица проектов не выровнена, страница по 50 строк;
5. таблица кейсов не выровнена и без листания вовсе.

Третье и четвёртое — не косметика: на 75 проектах страница в 50 строк листается
один раз и заканчивается, а таблица кейсов показывала 50 строк без всякого
способа увидеть остальные.
