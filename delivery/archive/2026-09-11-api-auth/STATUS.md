# Active delivery status

- **slug:** api-auth
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай Ф5» — на объявленный состав фазы: API, очередь, авторизация, права строками)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит: вход в сервис
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=bcrypt и PyJWT в манифесте с Ф1, здесь они впервые применяются
- **runtime_paths:** src/ahrefs_cases/api/deps.py reason=проверка прав проверяется исполнением: запрос без токена и запрос пользователя к чужому роутеру обязаны отличаться кодами, а не намерением
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** неудачный вход пишет в лог причину и почту, но никогда пароль; выданный токен виден в логе только временем жизни и группой
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Заглушка `current_group`, стоявшая с Ф1, заменяется настоящим источником:
токеном. Форма проверки не меняется — `require_right` был написан в Ф1 именно
так, чтобы Ф5 подставил источник, а не переписывал роутеры.

Попутно убирается вторая копия правила прав: свойства `can_*` у модели
пользователя не использовались нигде, а правило обязано иметь один ответ.
