# Active delivery status

- **slug:** campaigns-of-one-domain-pay-once
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_collect_scheme.py::test_two_campaigns_of_one_domain_ask_for_each_month_once
- **diagnosis:** n/a reason=причина известна и записана как Z8; соседний дефект Z15 найден живым прогоном этой же поставки
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026 — «давай z12 и так далее, в общем погоняй что осталось»)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («давай z12 и так далее», «выбери новые домены»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/collect/plan.py reason=экономия видна только там, где у домена есть вторая кампания: на калибровочном наборе таких нет, проверено нарочно заведёнными
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** в отчёте прогона по сайту с двумя кампаниями видно «месяцев перенесено», а смета не удваивается
- **observe_until:** 2026-10-08 (сдвинут 24.09.2026: до выкладки PR #7 прода не было — наблюдать было негде; окно отсчитано от выкладки, +14 дней. Сигнал про живые данные наблюдаем только после перевода в live — это решение владельца; не переведут к сроку — сдвиг с той же причиной)
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Z8 — первое правило ТЗ: ни один запрос к Ahrefs не делается дважды за одни и те
же данные. Агентство ведёт сайт несколькими кампаниями, проект опознаётся
тройкой `(домен, режим, начало периода)`, а ряды лежат с `project_id` — и кэш
видел только свой проект. Общие месяцы покупались по второму разу.

Живой прогон этой же поставки вскрыл **Z15**: «домен = проект» ломается на
второй кампании не только в деньгах. `collect --only` сверял количества и падал
с пустым списком имён; `explain` и `diagnose` брали `.first()` и молча
показывали одну кампанию из двух.
