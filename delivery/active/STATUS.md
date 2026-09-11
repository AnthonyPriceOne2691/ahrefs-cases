# Active delivery status

- **slug:** intake-api
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** tests/api/test_intake_api.py::test_estimate_uses_threshold_windows reason=внутри поставки чинится дефект окон, и он закрыт своим тестом
- **diagnosis:** delivery/active/diagnosis.md
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
- **new_dependency:** no reason=файл принимается телом запроса, а не multipart — python-multipart не нужен (решение в decisions.md)
- **runtime_paths:** src/ahrefs_cases/api/routers/runs.py reason=порядок объявления маршрутов проверяется исполнением: `/api/runs/estimate` обязан не попасть в `/{run_id}`
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** смета, показанная перед запуском, совпадает с `units_estimated` начавшегося прогона; расхождение означает, что окна точек снова разъехались
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Список доменов попадает в сервис только через CLI: человек из PR-отдела не может
загрузить файл, не позвав инженера. Экран загрузки — следующая поставка, и
питать его нечем: HTTP-приёма нет вовсе, а сметы прогона до старта нет ни у кого.

Здесь появляется вход по HTTP (файл или ссылка на Google Sheet) и ответ на
вопрос «во что обойдётся прогон и хватит ли квоты» — **до** того, как потрачен
первый unit.

Попутно чинится расхождение, найденное при осмотре: прогон из очереди собирал
не теми окнами точек, что прогон из CLI. Смета, показанная человеку, обязана
быть ценой того прогона, который запустит кнопка.
