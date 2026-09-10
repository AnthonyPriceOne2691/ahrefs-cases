# Active delivery status

- **slug:** collect-scheme-report
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
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony (примеры E9, E11, E14 подписаны до кода)
- **human_ok_plan:** n/a reason=класс S
- **runtime_paths:** none reason=правка касается отчёта, флага и чтения порогов в CLI; проверяется сквозным прогоном на фикстурах
- **observe_signal:** отчёт прогона печатает разбивку по способу и «стоимость запуска на 100 URL»; при `AHREFS_COLLECT_SCHEME=auto` смета на сотню доменов равна 10 000 против 19 800; способ сбора виден в снимке параметров прогона
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
