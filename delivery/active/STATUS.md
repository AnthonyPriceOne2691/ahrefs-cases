# Active delivery status

- **slug:** source-is-required
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_source_is_required.py
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-12 by=human:anthony (живой прогон по просьбе владельца; дефект найден в нём и блокирует Ф7)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** scripts/run_collect.py reason=дефект виден только в живом режиме: на фикстурах умолчание совпадает с истиной
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** reason=снято умолчание аргумента `source`; инварианты «Содержания кейса» и «Обзора продукта» не затронуты — правило про источник данных записано в рантбук живого прогона, которому оно и принадлежит by=human:anthony
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** в живом режиме классификация, пересчёт и предпросмотр читают живые ряды, а не фикстуры
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Живой прогон 12.09.2026 собрал пять доменов настоящими данными — и
классификация объявила «данных не хватает» по всем пяти. Причина: у
`classify_all`, `recalc`, `preview` и `diagnose` источник рядов —
**аргумент с умолчанием `MetricSource.FIXTURE`**, и вызывающие его не передают.

Это **третье повторение урока L53** (первое — preflight сверял смету с
фикстурной квотой, второе — карточка проекта показывала пустые графики).
Поэтому чинится не вызов, а возможность промолчать: умолчание убирается.
