# Active delivery status

- **slug:** contour-wave-0
- **stack:** delivery@1.88, cqg@absent, okf@absent
- **class:** S
- **kind:** bootstrap
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** n/a reason=класс S, §2.2 — достаточно tasks
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** weak
  <!-- CQG не развёрнут: волна В1, предельный срок — начало Ф2 (docs/CONTOUR_ROLLOUT.md).
       Что дёшево и не сделано: ruff/mypy/pre-commit ставятся одной волной вместе
       с baseline-ratchet; ставить их врозь значит снимать снимок дважды. -->
- **behavior-oracles:** weak — дёшево: прогон `scripts/delivery_check.py` в CI (CI нет, волна В1); кода продукта ещё нет, поведенческие тесты приходят в Ф2 вместе с ядром сбора
- **artifact_oracle:** n/a reason=проект пока ничего не собирает; PDF появится в Ф4
- **ci-oracles:** weak
  <!-- CI не развёрнут (волна В1). Класс S — waiver не требуется. -->
- **worktree:** none (S)
- **hooks:** not-deployed
- **blockers:** none
- **waivers:** none
- **new_dependency:** none
- **runtime_paths:** none reason=кода нет; объявляются в Ф2 (живой Ahrefs — сеть и квота) и Ф4 (PDF — системные библиотеки WeasyPrint)
- **model_surface:** n/a reason=в MVP текст кейса шаблонный, модель не вызывается; ось ⑤ придёт волной В3 перед мержем LLM-ветки
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** развёрнутый контур отклоняет: `delivery_check.py` краснеет на STATUS с несогласованными правами или пустой фазой
- **observe_until:** 2026-09-24
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Названный остаток (вариант D)

- `git add -f` обходит `.git/info/exclude` — на репозитории, который станет чужим,
  закрыть нечем. Остаток назван, а не замолчан (AGENT_STACK §7.1a).
- `stack-selftest: external (~/Documents/Prepare)` — шаг «Canon payload selftest»
  в CI проекта невозможен: текстов канонов там нет по построению. Самопроверка
  гоняется там, где лежат каноны, руками при каждой правке.
