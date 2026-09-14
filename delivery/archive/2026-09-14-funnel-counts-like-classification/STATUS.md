# Active delivery status

- **slug:** funnel-counts-like-classification
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_collect_funnel.py::test_funnel_measures_growth_like_classification
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony (калибровочный прогон по просьбе владельца; дефект найден им и искажает калибровку)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/collect/funnel.py reason=расхождение видно только на живых сезонных рядах: синтетика в тестах монотонна
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** проект, который классификация считает выросшим, получает подтверждающие метрики — воронка не отсекает его раньше
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Калибровочный прогон 14.09.2026 на 25 живых доменах: двое из десяти публично
признанных победителей не могли стать «хорошими» **ни при каких порогах**.

Предварительный отбор кандидатов шага 2 считает рост крайними точками ряда
(`последняя / первая`), а классификация — средними по окнам версии порогов. На
сезонных сайтах это разные числа:

```
wineverygame.com   воронка 0.93×   классификация 1.86×
wickes.co.uk       воронка 1.03×   классификация 1.48×   (порог воронки 1.10×)
```

Воронка решает «не растёт», подтверждающие метрики не покупаются — и в вердикте
стоит «подтверждающая: факт —», что читается как «не выросла». Проект,
достойный кейса, не получит его никогда, а отчёт назовёт неверную причину.
