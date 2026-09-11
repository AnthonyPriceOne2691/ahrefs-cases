# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам — см. дайджест ниже)
**CI run:** <ссылка на зелёный прогон после этого коммита>
**Commit:** 455208e

## Shape oracles
- [x] PASS — pre-commit, 29 хуков, упавших 0
- [x] PASS — предохранители: net_loc 604 при пороге 800

## Behavior oracles
- [x] PASS — pytest 288 passed, 1 skipped
- [x] PASS — одиннадцать тестов ступени по примерам E1–E10

## Product oracles
- [x] PASS — ступень покупает только недостающую середину кривой: 294 units
- [x] PASS — стоимость трафика и DR берутся числами: по 100
- [x] PASS — смета на десяти кейсах 4 940; повторный запуск не покупает ничего

## Ревью рисковых мест

**Деньги.** Поставка **добавляет** расход, а не снимает: 4 940 units на десять
кейсов. Обоснование в спеке: ТЗ прямо требует динамику позиций, а по двум
точкам её не показать. Рычаг экономии — состав полей (`KEYWORDS_GRAPH.select`
из двух корзин вместо пяти) и докупка только дыры (`cache.missing_span`), без
них та же информация стоила бы 969 на кейс.

**Безопасность.** Риска нет: новых входов извне не появилось, дифф трогает
`collect/endpoints.py`, `collect/plan.py`, `collect/cache.py`,
`collect/runner.py`, новый `collect/fetch.py`, `classify/series.py` и
`scripts/run_collect.py`.

**Транзакция БД.** `build_case_plan` только читает; запись осталась в
`runner._store_outcome`. `missing_span` — один `select` с `group_by` по месяцу
и `having` по числу метрик: он спрашивает «есть ли **все** метрики в этом
месяце», иначе месяц с половиной корзин считался бы купленным.

**Производительность.** Ступень добавляет три запроса на кейс (один за кривую,
два за числа) — десять проектов, тридцать запросов. Меньше, чем шаг 2 на
тридцати кандидатах.

**Интеграция.** DR переехал со ступени 2 на ступень 3 и потерял флаг: это
меняет состав шага 2 и поведение `stage2_specs()`. Обновлён тест, который
проверял флаг; остальные флаги (`pages`, `search_volume`) живы и проверяются
там же. `_TaskOutcome` и `_fetch_one` стали публичными в новом модуле
`collect/fetch.py` — раннер второй раз упёрся в лимит длины.

**Канон.** Гейт синхронности потребовал обновить четыре концепта: схему сбора
(появилась третья ступень), покрытие (третий вопрос к кэшу), модель стоимости
(состав полей как рычаг) и рантбук (цена прогона 33 560). Все обновлены.

## Assertion digest (ревью ожиданий, не кода)

База: `ce66b78` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **34**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
E2	assert KEYWORDS_GRAPH.path == KEYWORDS_HISTORY.path, "ручка та же"
E2	assert KEYWORDS_GRAPH.select == ("date", "top3", "top4_10")
E2	assert KEYWORDS_GRAPH.row_units() == 21
E2	assert KEYWORDS_HISTORY.row_units() == 51
E2	assert KEYWORDS_GRAPH.estimate_units(15) == 315
E2	assert KEYWORDS_HISTORY.estimate_units(15) == 765
E1	assert KEYWORDS_GRAPH.needs_series is True, "E1: кривая покупается серией"
E4	assert METRICS_VALUE.needs_series is False, "E4: стоимость трафика — число"
E4	assert 2 * KEYWORDS_GRAPH.estimate_units(2) < KEYWORDS_GRAPH.estimate_units(19), (
L27	assert span == (date(2025, 3, 1), date(2026, 4, 1)), "середина между купленными границами"
L27	assert len(curve) == 1
L27	assert curve[0].expected_rows() == 14
L27	assert curve[0].estimated_units() == 294, "14 строк по 21 — платим только за дыру"
E4	assert choice.scheme is CollectScheme.TWO_POINTS
E4	assert len(value_tasks) == 2
E4	assert sum(task.estimated_units() for task in value_tasks) == 100
E3	assert at_start == set(KEYWORDS_HISTORY.metrics.values()), "на границе все пять корзин"
E3	assert set(KEYWORDS_GRAPH.metrics.values()) < at_start, "кривая берёт подмножество"
E7	assert curve == []
E7	assert any("уже куплена целиком" in item.reason for item in plan.cached)
E8	assert plan.estimated_units() == 4_940
E8	assert len(STAGE3_SPECS) == 3, "кривая позиций, стоимость трафика и DR"
E8	assert per_case == 494, "294 за дыру в кривой, 100 за стоимость трафика, 100 за DR"
L33	assert choice.scheme is CollectScheme.TWO_POINTS, "в кейсе DR это «было → стало»"
L33	assert sum(task.estimated_units() for task in tasks) == 100
L33	assert choice.units_full_history == 198, "историей стоил бы вдвое дороже: 18 строк по 11"
E9	assert (metric in FLOW_METRICS) is flow
E9	assert aggregate(by_month, months, flow=flow) == expected
E9	assert aggregate(one_month, months, flow=True) == 500.0, "E9: пустой месяц не ноль"
E9	assert aggregate({}, months, flow=True) is None, "E9: нет данных — не ноль"
L33	assert DOMAIN_RATING_HISTORY not in stage2_specs(), "DR не платится кандидатам"
L33	assert DOMAIN_RATING_HISTORY.stage == 3
L33	assert PAGES_HISTORY not in stage2_specs()
L33	assert PAGES_HISTORY in stage2_specs()
```

✅ **Каждое утверждение ведёт к примеру спеки** (E1 E2 E3 E4 E7 E8 E9 L27 L33), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Spec coverage gaps
- «Число ключей» из must-have ТЗ считается суммой пяти корзин распределения —
  это свойство API, замером не подтверждённое. Записано в `docs/FINDINGS.md`.
- UR, backlinks и «новые/потерянные домены» из must-have списка не собираются:
  history-endpoint'ов под них в разведке нет, и в блоках кейса по ответам
  заказчика их тоже нет. Решение названо здесь, а не замолчано.

## Verdict
- [x] READY FOR HANDOFF

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base ce66b78 -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 11 code (+11 process docs) / +713/-106 (net +607) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 commit(s) after first phase: handoff |
| harness_hardened | yes — scripts/lint/jscpd_baseline.txt, tests/test_collect_case_step.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
