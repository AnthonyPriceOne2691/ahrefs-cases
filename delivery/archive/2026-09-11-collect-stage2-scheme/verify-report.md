# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** human:anthony at=2026-09-11 — два утверждения (пример E9, граница у `refdomains-history`) придуманы при реализации и внесены в спеку явной строкой; подпись опирается на инструкцию «делаем шаг 2 сначала» и на принятый маршрут, а не на отдельное чтение этих строк
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34581356827
**Commit:** 91c102d

## Shape oracles
- [x] PASS — pre-commit, 29 хуков, упавших 0
- [x] PASS — предохранители: net_loc в пределах порога, waiver не потребовался

## Behavior oracles
- [x] PASS — pytest 277 passed, 1 skipped
- [x] PASS — десять тестов шага 2 по примерам E1–E5, E7–E9

## Product oracles
- [x] PASS — смета шага 2 на тридцати кандидатах: 8 820 units против 30 240
- [x] PASS — у одного проекта два разных способа, отчёт показывает оба
- [x] PASS — golden-таблица классификации зелёная: подтверждающие метрики
  считаются по тем же точкам

## Ревью рисковых мест

**Деньги.** Здесь их больше всего за всю перестройку: `keywords-history` стоил
918 units на кандидата и стал стоить 204. Риск в обратную сторону — купить
меньше, чем нужно вердикту: подтверждающие условия считаются по точкам А и Б
(`classify/points.py`), а окно запроса берётся из версии порогов, поэтому
точка считается по тем же месяцам, что и раньше. Проверено golden-таблицей.

**Безопасность.** Риска нет: новых входов извне не появилось, дифф трогает
`collect/plan.py`, `collect/scheme.py`, `config/ahrefs.py` (докстринг) и тесты.

**Транзакция БД.** Не затронута: `build_stage2_plan` только читает, запись
осталась в `runner._store_outcome` без изменений.

**Производительность.** Число задач на шаге 2 выросло: у `keywords-history`
два запроса вместо одного. На тридцати кандидатах это 90 задач вместо 60 — при
`COLLECT_MAX_PARALLEL` = 3 прогон удлинится, но каждая задача стала дешевле и
короче (две строки против девятнадцати). Реальную скорость меряет Ф7, шаг 6.

**Интеграция.** `CollectPlan.choices` сменил ключ с проекта на пару
«проект + endpoint» — это тронуло разбивку отчёта и два теста, которые считали
«проекты × endpoint'ы». Оба обновлены осознанно: старая формула перестала быть
верной, потому что число запросов теперь зависит от схемы каждого endpoint'а.

**Канон.** Гейт синхронности поймал устаревшую цену прогона в
`knowledge/ops/first-live-run.md` — 27 330 против нынешних 28 620. Обновлены
рантбук и концепт схемы сбора.

## Assertion digest (ревью ожиданий, не кода)

База: `88bcf7c` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **40**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
E1	assert by_endpoint["keywords-history"] == len(GROWING) * 2, "E1: две точки — два запроса"
E2	assert by_endpoint["refdomains-history"] == len(GROWING), "E2: история — один запрос"
E3	assert report.requests_made == sum(by_endpoint.values()), "E3: счёт запросов сходится"
L13	assert report.projects_total == len(GROWING), "проектов столько же, сколько кандидатов (L13)"
L13	assert breakdown.projects(CollectScheme.TWO_POINTS) == 1
L13	assert breakdown.projects(CollectScheme.FULL_HISTORY) == 1
L13	assert breakdown.units() == 155
L13	assert all(
E1	assert KEYWORDS_HISTORY.row_units() == 51, "10 × 5 полей + 1"
E1	assert choice.scheme is CollectScheme.TWO_POINTS
E1	assert choice.units_two_points == 204
E1	assert choice.units_full_history == 918
E1	assert "714" in choice.reason, "экономия названа числом"
E1	assert REFDOMAINS_HISTORY.row_units() == 5
E1	assert choice.scheme is CollectScheme.FULL_HISTORY
E1	assert choice.units_full_history == 90
E1	assert choice.units_two_points == 100
E4	assert REFDOMAINS_HISTORY.rows_under_minimum() == 10
E4	assert choice.scheme is CollectScheme.FULL_HISTORY
E4	assert "перекрыл" in choice.reason
E9	assert short.scheme is CollectScheme.FULL_HISTORY, "E9: 19 строк — история"
E9	assert long.scheme is CollectScheme.TWO_POINTS, "E9: 31 строка — точки"
E9	assert long.units_full_history > long.units_two_points
L13	assert schemes["keywords-history"] is CollectScheme.TWO_POINTS
L13	assert schemes["refdomains-history"] is CollectScheme.FULL_HISTORY
L13	assert len(plan.tasks) == 3, "две точки по ключам плюс одна история по ссылкам"
L13	assert breakdown.projects(CollectScheme.TWO_POINTS) == 1
L13	assert breakdown.projects(CollectScheme.FULL_HISTORY) == 1
L13	assert "keywords-history two_points: 1 проект(ов)" in lines
L13	assert "refdomains-history full_history: 1 проект(ов)" in lines
E5	assert plan.estimated_units() == 8_820
E5	assert breakdown.units_if_history == 30_240
E5	assert breakdown.units_if_auto == 8_820
E5	assert "экономия 21420" in "\n".join(breakdown.as_lines())
Z6	assert traffic_gap == 0, "серия трафика плотная — по ней и судит правило"
Z6	assert keywords_gap == 8, "у ключей дыра восемь месяцев, и она намеренная"
E8	assert len(keywords_tasks) == 2
E8	assert len([task for task in second.tasks if task.spec is KEYWORDS_HISTORY]) == 1
E8	assert any("уже куплено" in item.reason for item in second.cached)
E4	assert spec.rows_under_minimum() == expected_free_rows, "E4: ёмкость минимума — следствие цены"
```

✅ **Каждое утверждение ведёт к примеру спеки** (E1 E2 E3 E4 E5 E8 E9 L13 Z6), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Spec coverage gaps
- Цена строки `keywords-history` (51) и `refdomains-history` (5) замером не
  подтверждена. Если Ф7 покажет другую — сторона выбора у `refdomains` может
  смениться, и это будет видно в отчёте, а не в счёте Ahrefs.

## Verdict
- [x] READY FOR HANDOFF

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base 88bcf7c -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 6 code (+7 process docs) / +356/-68 (net +288) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 commit(s) after first phase: handoff |
| harness_hardened | yes — tests/test_collect_stage2_scheme.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
