# Active delivery status

- **slug:** case-narrative
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай» — на предложенный состав: текст по числам, сверка, подсветка, запись `Case`)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** tests reason=текст проверяется на готовом кейсе: каждое число в предложении сверяется с числами структуры
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=текст шаблонный, модель не вызывается
- **runtime_paths:** src/ahrefs_cases/cases/store.py reason=версионирование кейса проверяется только исполнением: повторный `render` обязан дать вторую версию, а не переписать первую
- **model_surface:** n/a reason=текст шаблонный; ось ⑤ придёт волной В3 перед первым вызовом модели
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `render <домен>` печатает версию записанного кейса и контрольную сумму файла; повторный запуск показывает версию 2 — видно, что перегенерация не затирает прошлый кейс
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Лист начинает говорить словами, и вместе с этим появляется риск, которого до сих
пор не было: цифру в предложении никто не сверяет глазами. Поэтому текст
собирается не «по шаблону», а по числам кейса, и каждое число в готовом тексте
сверяется с ними механически — не совпало, текста нет вовсе.

Здесь же кейс впервые попадает в базу: `Case` с версией и `CaseArtifact` с
контрольной суммой. Перегенерация через полгода — требование ТЗ, и она обязана
добавлять версию, а не затирать прошлую.
