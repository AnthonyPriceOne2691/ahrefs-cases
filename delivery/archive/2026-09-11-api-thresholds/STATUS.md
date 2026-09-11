# Active delivery status

- **slug:** api-thresholds
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай Ф5» — на объявленный состав фазы, включая права и алерты)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=всё уже в манифесте
- **runtime_paths:** src/ahrefs_cases/api/routers/rulesets.py reason=различие прав проверяется исполнением: пользователь обязан получать 403 на сохранении и 200 на предпросмотре, и это разные вызовы одного экрана
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `GET /api/alerts` отвечает списком поводов с числами (остаток units, номер упавшего прогона, готовая пачка); пустой список — это ответ «поводов нет», а не тишина
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Ради этого ТЗ и развело три группы: пороги правят Head of Link Building и Owner,
пользователь — нет. Право проверяется зависимостью на роутере, а не условием в
обработчике, и различие видно по вызовам одного экрана: предпросмотр открыт
всем, сохранение и активация — нет.

Вторым приходит мониторинг units, который заказчик просил прямо: сервис сам
называет поводы — остаток, упавший прогон, готовая пачка.
