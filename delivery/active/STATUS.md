# Active delivery status

- **slug:** one-answer-about-coverage
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_classify_coverage_agreement.py::test_classification_and_preview_agree
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («протестировать всё в сервисе… чтобы осталась только калибровка» — дефект найден этой проверкой и блокирует её)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/classify/coverage.py reason=расхождение видно только на живом стенде: тесты классификации строят серии сами и всегда покрывают период целиком
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** классификация, предпросмотр и пересчёт отвечают про один проект одинаково; после активации версии ни один проект не остаётся без вердикта молча
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Сплошная проверка сервиса 13.09.2026 нашла расхождение, которое ломает саму
калибровку (Ф8).

Про один и тот же проект система отвечает **тремя разными способами**:

- `classify` — «good», с числами по каждому условию;
- `preview` — «не хватает данных: точка А 2024-06»;
- `recalc` — пропускает, вердикт не пишет вовсе.

После активации новой версии порогов девять проектов из девятнадцати **остались
без вердикта**: карточка показывает пустоту, экран проектов — «не
классифицирован», и почему — не сказано нигде. Калибровка состоит ровно из
«поменяли порог → пересчитали → сверили с экспертом», и на этом шаге половина
списка молча исчезает.

Причина — два правила об одном и том же. `classify/coverage.py` считает
непокупленным любой месяц вне собранной серии и запрещает вердикт;
`rules._truncated_history` считает тот же случай справочной записью и вердикт
разрешает, прямо говоря «группу она не меняет — решает человек».
