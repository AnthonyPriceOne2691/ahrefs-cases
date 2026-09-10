# Active delivery status

- **slug:** collect-scheme-stage1
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix; расчёт, из которого выросла поставка, — docs/UNITS_OPTIMIZATION.md
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** pending — спека E1–E12 коммитится до кода
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
  <!-- Вторая поставка по правилу размера (урок L20). Ф3б открывалась как первая
       и уступила место хотфиксу Z1; её спека жива в коммите 9990114. -->
- **new_dependency:** none reason=схема считается по существующей модели стоимости endpoints.py
- **runtime_paths:** src/ahrefs_cases/collect/scheme.py, src/ahrefs_cases/collect/plan.py reason=цена схемы проверяется только исполнением — тесты сверяют смету с моделью, а не с Ahrefs; доказательство на handoff — сквозной прогон collect на фикстурах со сверкой сметы и журнала units (урок L13: несходящийся отчёт нашёлся прогоном, а не тестом), живая цена — Ф7 п.6
- **model_surface:** n/a reason=текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Почему это идёт раньше Ф3б

Ф3б считает вердикты по тому, что уже куплено, и от схемы сбора не зависит —
но зависит наоборот: пороги задают окна точек, а окна задают цену схемы (E4).
Перестройка сбора первой означает, что Ф3б садится на готовые окна, а не
переписывается вслед за ними.

Второй довод — деньги: пока шаг 1 стоит 441 unit на домен, любой живой прогон
съедает бюджет заказчика на четверти списка. Ф3б это не лечит, а Ф7 без этого
невозможна.

## Границы поставки

Два модуля: `collect/scheme.py` (новый, чистый) и `collect/plan.py` (правка).
Плюс одно поле в `collect/endpoints.py` и разбивка в отчёте прогона.

Шаг 2 окнами — следующая поставка, история под график — Ф4. Резать заранее, а
не дописывать пришедшее в открытую поставку (урок L15).
