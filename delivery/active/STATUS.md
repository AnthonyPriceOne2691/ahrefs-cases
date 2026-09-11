# Active delivery status

- **slug:** collect-stage2-scheme
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («делаем шаг 2 сначала» — состав объявлен маршрутом в docs/UNITS_OPTIMIZATION.md, принятым 11.09.2026)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=схема уже написана, меняется область её применения
- **runtime_paths:** src/ahrefs_cases/collect/plan.py, src/ahrefs_cases/collect/scheme.py reason=цена схемы проверяется только исполнением; доказательство — сквозной прогон шага 2 на фикстурах со сверкой сметы и числа строк, живая цена строки keywords и refdomains — Ф7 п.6
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Почему это следующая поставка

Самая большая оставшаяся экономия и единственная, которую ничто не блокирует.
Правило достоверности серии смотрит только на `org_traffic`, то есть на шаг 1 —
разреженность шага 2 вердикту не мешает (Z6 сюда не дотягивается).

Числа посчитаны по замеренной формуле, а не оценены: на кандидата шаг 2 стоит
**1008 units историей и 294 точками**, на тридцати кандидатах — 30 240 против
8 820. Прогон целиком по ТЗ: 50 040 → **28 620**.
