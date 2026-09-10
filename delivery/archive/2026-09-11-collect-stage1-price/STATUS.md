# Active delivery status

- **slug:** collect-stage1-price
- **class:** S
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** проверочные копии (`git worktree`) на каждый коммит дробления
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none
- **model_surface:** n/a reason=текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony (примеры E8, E9 подписаны до кода)
- **human_ok_plan:** n/a reason=класс S
- **runtime_paths:** none reason=правка касается состава запроса и умолчания конфига; проверяется тестами и сквозным прогоном на фикстурах
- **observe_signal:** смета прогона на сотню доменов равна 19 800 units (было 44 100); шаг 1 запрашивает ровно одно поле `org_traffic`; окно запроса не начинается раньше `period_start`, если пороги не просят baseline
- **observe_until:** 2026-09-25

## Откуда дробление

Работа была написана одной поставкой и дала net loc_diff 990 при пороге 800.
Waiver решено не брать: третий подряд после Ф2б (2521) и Ф3а (1584) отменил бы
правило размера, введённое из-за них же. Поставка разрезана на три по 154 / 784
/ 94 строки; итоговое дерево совпало с неразрезанным до последней строки
(`git diff` пуст).

Границу подсказал гейт: первая попытка разрезать иначе — чистое правило
отдельно от провода — дала два clone-пары (арифметика месяцев жила бы в двух
местах) и отказ mypy на двух мелочах из другой половины. Гейт копипаста
оказался индикатором границы поставки, а не только стиля.
