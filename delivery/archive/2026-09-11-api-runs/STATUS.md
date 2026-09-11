# Active delivery status

- **slug:** api-runs
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай Ф5» — на объявленный состав фазы: API, очередь, авторизация, права)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефакты собирает задача кейсов, проверены своей поставкой
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=rq и redis в манифесте с Ф1, здесь впервые применяются
- **runtime_paths:** src/ahrefs_cases/workers/jobs.py reason=фоновая задача проверяется исполнением: у неё своя сессия и свой процесс, и упавшая задача обязана оставить прогон `failed`, а не «идёт» навсегда
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `GET /api/runs` показывает статус, число проектов и потраченные units по каждому прогону; второй запуск при активном прогоне отвечает 409 с его номером
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Прогон запускается из сервиса и идёт в фоне. Очередь — интерфейс с двумя
реализациями, как провайдер Ahrefs: на машине разработчика Redis может не быть,
а сервис должен работать, и выбор делает конфиг, а не то, какой модуль первым
дошёл до очереди.

Замок на второй прогон — не удобство, а деньги: шесть человек запускают один и
тот же список, и второй прогон стоит вторую цену.
