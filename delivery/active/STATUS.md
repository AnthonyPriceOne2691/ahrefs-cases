# Active delivery status

- **slug:** next-day-probe
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** tooling
- **repro_test:** n/a reason=не дефект; инструмент замера, который проверяется собственным запуском
- **diagnosis:** n/a reason=не дефект, а инструмент замера
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («сделать всё до калибровочных кейсов»; хвост Ф7 назван первым)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** scripts/probe_next_day.py reason=ответ на оба вопроса даёт только живой ключ; на фикстурах скрипт обязан отказаться работать
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** снимок сравнивается с предыдущим и называет вердикт по H2; счётчик ключа сверяется с журналом, а не с памятью
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Ф7 держат два вопроса, на которые нельзя ответить за один заход:

1. **Закрыт ли текущий месяц** (H2). Если Ahrefs достраивает прошлый месяц
   позже, кэш «закрытые месяцы неизменяемы» навсегда сохранит неполные данные
   и не скажет об этом. Проверяется одним и тем же доменом в два разных дня.
2. **Считает ли Ahrefs наш расход** (`units_usage_api_key`). 12.09 счётчик не
   сдвинулся ни разу при ~2 262 потраченных units, а `-total-actual` пришёл
   нулём. Если счётчик не растёт вообще, `preflight` всегда видит полный лимит
   — предохранитель написан, вызывается и ничего не охраняет.

Поставка даёт инструмент, а не ответ: ответ снимает человек живым ключом.
