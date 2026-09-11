# Active delivery status

- **slug:** docker-prod
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** chore
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («дев и прод, двумя поставками», фронт — «nginx отдельным контейнером»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** боевые образы собираются и отвечают: `docker compose build`, `up`, живой запрос к `/` и `/api/health` через nginx на 8080
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no reason=новых пакетов нет; добавляется образ nginx
- **runtime_paths:** docker-compose.yml reason=боевой компоуз проверяется только исполнением; прочитанный компоуз ничего не доказывает (урок L69)
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на сервере агентства сервис поднимается тем же компоузом, что проверен здесь; статика отдаётся nginx, а не dev-сервером, и `/api` уходит в бэкенд
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Дев-окружение поднимается целиком, но на сервер его везти нельзя: там vite
раздаёт исходники, секреты лежат в файле компоуза, а исходники монтируются с
машины. Боевой путь до сих пор не существует ни в каком виде — а Ф9 начнётся с
того, что его попросят.

**Боевой путь, который никто не гонял, протухает молча** (урок L69 — та же
причина, по которой дев-компоуз оказался несобираемым). Поэтому он собирается и
поднимается здесь, на той же машине, до всякого сервера.
