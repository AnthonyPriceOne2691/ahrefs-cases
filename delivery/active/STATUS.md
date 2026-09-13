# Active delivery status

- **slug:** estimate-by-measured-prices
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** chore
- **repro_test:** tests/test_units_profile.py::test_documents_carry_the_number_the_model_computes
- **diagnosis:** n/a reason=не дефект кода: код считает по замеренным ценам, устарели документы
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («плюс пересчёт сметы под боевой список» — выбрано в списке работ до калибровки)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=считает по спекам в коде, к сети не ходит
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** число «сколько стоит прогон по ТЗ» в документах и в канонe совпадает с тем, что считает модель цены
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Замер 12.09.2026 показал, что **у каждого поля своя цена**: ключевой бакет стоит
1 unit, трафик — 10. Код исправлен в тот же день, а документы и канон остались с
прежней моделью «10 за любое поле». Разница не косметическая: строка
`keywords-history` там названа 51 unit, а стоит 6 — шаг 2 завышен втрое.

Заказчику названо «27 330 units, лимит от 30 000», в каноне живёт «33 560,
лимит от 40 000». Ни одно из этих чисел не посчитано по действующей модели.

Поставка считает профиль прогона **кодом**, вставляет таблицу в документ
генератором и держит совпадение оракулом: число, посчитанное пером, расходится
с моделью молча — это ровно то, чем кончились обе прежние редакции.
