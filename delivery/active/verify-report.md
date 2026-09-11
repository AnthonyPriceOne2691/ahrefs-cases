# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам — см. дайджест ниже)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34577806763
**Commit:** 929fc77

## Shape oracles
- [x] PASS — pre-commit, 27 хуков, упавших 0
- [x] PASS — предохранители: net_loc 632 при пороге 800, файлов 6 при пороге 25; waiver не потребовался

## Behavior oracles
- [x] PASS — pytest 249 passed, 1 skipped
- [x] PASS — девять тестов пересчёта по примерам E1, E4–E7, E9, E10

## Product oracles
- [x] PASS — `recalc <версия>` считает по уже купленным данным и печатает распределение по группам и пропуски
- [x] PASS — golden-таблица классификации не изменилась: разделение расчёта и записи поведение не тронуло

## Что уточнилось при реализации
Пример E9 в спеке описывал «версия просит окно 6, а куплено 4». При реализации
выяснилось, что этот случай достижим только для проекта, собранного двумя
точками, то есть за флагом, и им уже занимается правило достоверности серии
(Z6). Достижимая форма E9 — месяцы **до старта работ**: их покупает только
версия, у которой включён `pre_start_baseline_months`. Проверка написана по
достижимой форме, различитель закреплён отдельным тестом.

## Spec coverage gaps
- E2, E3, E8 (предпросмотр) — следующая поставка, как и было объявлено.

## Assertion digest (ревью ожиданий, не кода)

База: `7be377a` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **20**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
E1	assert report.recalculated == 1
E1	assert len({verdict.ruleset_id for verdict in verdicts}) == 2, "две версии, два вердикта"
E4	assert [ruleset.id for ruleset in active] == [activated.id]
E4	assert after == before, "активация не переписывает прошлые вердикты"
E5	assert count == 1
E6	assert report.total == 10
E6	assert report.recalculated == 10
E6	assert sum(report.by_group.values()) == 10
E7	assert "2026-09-F" in str(excinfo.value), "в ошибке перечислены доступные версии"
E9	assert report.recalculated == 0
E9	assert [item.domain for item in report.skipped] == ["baseline.example.com"]
E9	assert "baseline до старта" in report.skipped[0].reason
E9	assert "2024-10" in report.skipped[0].reason, "месяцы названы, а не сосчитаны"
E9	assert written == 0, "вердикт по неполному окну не выдаётся вовсе"
E10	assert report.skipped == []
E10	assert report.recalculated == 1
E10	assert "пропущено 0" in "\n".join(report.as_lines())
E9	assert report.skipped == []
E9	assert report.by_group.get(Group.INSUFFICIENT_DATA) == 1
E9	assert gap.is_empty
```

✅ **Каждое утверждение ведёт к примеру спеки** (E1 E10 E4 E5 E6 E7 E9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Ревью рисковых мест

**Деньги.** Прямого расхода нет и быть не может: `recalc` и `compute_verdict`
не касаются провайдера, и это проверяется падающим `httpx` в фикстуре
`no_network`, а не докстрингом. Косвенный риск в другую сторону: проект,
попавший в `report.skipped`, не получает вердикт — если пропусков окажется
много, оператор может решить «докупить всё» и потратить лишнее. Поэтому
пропуск называет **месяцы**, а не число: по ним видно, чинится это включением
baseline обратно или покупкой.

**Транзакция БД.** `recalc` пишет через тот же `store` с
`on_conflict_do_update` по `uq_verdict_project_ruleset`, что и классификация, и
делает `flush`, а не `commit`: коммит остаётся у вызывающего (CLI). Это
сохраняет откат в тестах (урок L8: чужие данные возвращает откат) и не даёт
пересчёту зафиксировать половину результата при ошибке в середине.
`activate` перебирает все версии и ставит `is_active` — записей единицы, полный
перебор здесь дешевле выборочного обновления и не оставляет двух активных.

**Производительность.** Пересчёт читает серию отдельным запросом на проект:
на сотне проектов это сто запросов к `metric_points`. Осознанно: пересчёт
запускают на калибровке по десяткам доменов, не в цикле прогона, а общий
`selectin` усложнил бы чтение ради невидимой выгоды. Если Ф8 покажет
медленный пересчёт — это правка одного места, `series.load_series`.

**Интеграция.** `classify_project` разобран на `compute_verdict` + `store`.
Риск — поведение Ф3а: у неё golden-таблица и девять тестов вердиктов, все
зелёные без единой правки, потому что разбор не тронул ни одного условия.
Публичной стала `store` (была `_store`): у неё теперь два вызывающих, и оба в
`classify/`.

**Новый модуль.** `classify/coverage.py` чистый: месяцы на входе, месяцы на
выходе. Его главный риск — не ошибка расчёта, а **ложная тревога**:
предупреждение, срабатывающее когда всё в порядке, обесценивается за неделю.
Поэтому нехваткой считаются только месяцы вне собранного отрезка, и на это
стоит отдельный тест (дыра внутри отрезка — не нехватка).

## Verdict
- [x] READY FOR HANDOFF

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base 7be377a -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 6 code (+3 process docs) / +644/-12 (net +632) |
| commits | 1 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_classify_recalc.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
