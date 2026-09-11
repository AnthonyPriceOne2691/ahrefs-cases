# Active delivery status

- **slug:** case-zip
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай» — на состав последней поставки Ф4: нейминг по ТЗ и ZIP)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** tests reason=архив открывается тестом: состав, имена по ТЗ и список внутри
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=zipfile из стандартной библиотеки
- **runtime_paths:** src/ahrefs_cases/export/archive.py reason=пачка проверяется исполнением: кейс с запретом обязан выпасть из архива, а не попасть в него молча
- **model_surface:** n/a reason=текст шаблонный; ось ⑤ придёт волной В3 перед первым вызовом модели
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `pack` печатает путь архива, число кейсов внутри и отдельно — кто не попал и почему (запрет, группа, нет данных)
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Кейсы начинают уходить пачкой, как требует ТЗ, и получают имена по его правилу.

Второе, менее очевидное: архив — единственный предохранитель перед публикацией.
Ревью черновика ТЗ не предусматривает, значит смотреть будут ZIP, и он обязан
помогать смотреть: список с группой и пометкой «можно публиковать» лежит внутри.
