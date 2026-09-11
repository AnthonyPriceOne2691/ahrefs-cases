# Active delivery status

- **slug:** api-users
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай сделаем раздачу прав от администратора… можно генератор паролей туда сделать… посмотри, как это реализовано в CRM»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=bcrypt и secrets уже есть; миграция на существующей схеме
- **runtime_paths:** src/ahrefs_cases/api/routers/users.py reason=перекрытие права проверяется исполнением: личное решение обязано побеждать групповое в обе стороны, и это видно только запросом от конкретного человека
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `GET /api/users` показывает у каждого группу, активность и личные права; выданное точечно право видно строкой, а не выводится из роли
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Список сотрудников от заказчика перестаёт быть блокером: администратор заводит
людей сам, с генерируемым паролем, и сам решает, кому что можно.

Из CRM агентства перенесён приём, который делает это растяжимым: роль даёт набор
прав, а **личное право перекрывает роль** в обе стороны. Новое право не требует
новой группы — и не требует правки кода, чтобы выдать его одному человеку.
