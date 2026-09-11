# Active delivery status

- **slug:** docker-dev
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** chore
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («полностью весь сервис упаковать в Docker-контейнеры… и фронт, и back», нарезка «дев и прод, двумя поставками»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** образ собирается и отвечает: `docker compose build`, затем `up` и живой запрос к `/api/health` и к экрану на 5173
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no reason=новых пакетов нет; добавляется образ node для дев-фронта
- **runtime_paths:** docker-compose.dev.yml reason=компоуз проверяется только исполнением — собранный и поднятый, а не прочитанный
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** новый человек поднимает сервис одной командой и попадает на экран входа, не ставя ни python, ни node
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Сервис запускается по частям и руками: Postgres в докере, uvicorn и vite — на
машине, миграции — отдельной командой. Новому человеку (и серверу агентства)
нужно повторить всю эту последовательность, зная её.

Попутно чинится то, что нашлось при осмотре: **`.dockerignore` нет**, а дев-стадия
образа делает `COPY . .` — в контекст сборки уезжают `.venv` (319 МБ, собранный
под macOS и в Linux нерабочий) и `node_modules` (372 МБ). То есть образ api,
объявленный в компоузе с Ф1, ни разу не собирался по-настоящему.
