# Active delivery status

- **slug:** api-read
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай Ф5» — на объявленный состав фазы)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит; отдаёт уже собранные
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=FastAPI и Pydantic в манифесте с Ф1
- **runtime_paths:** src/ahrefs_cases/api/routers/cases.py reason=выдача файла проверяется исполнением: путь из базы может не существовать на диске, и это обязан быть 404, а не пустой ответ
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `/api/usage` показывает потраченное, зарезервированное и остаток одним ответом — до сих пор это было видно только в конце прогона в консоли
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Данные, которые сервис уже считает, становятся доступны по HTTP: список
проектов с группами, карточка с объяснением вердикта и рядами под графики,
библиотека кейсов со скачиванием и расход units.

Границы выдачи стоят по построению: лимит с потолком у каждого списка. Это не
формальность гейта — сотня проектов сегодня превращается в тысячи строк рядов
в карточке, и «отдать всё» перестаёт работать незаметно.
