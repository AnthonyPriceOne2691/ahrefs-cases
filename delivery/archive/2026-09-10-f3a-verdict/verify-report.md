# Verify report

**Date:** 2026-09-10
**Verifier:** human:anthony
**asserts_reviewed_by:** human:anthony at=2026-09-10 — подписаны D14–D20, дописанные по ходу, и исправленная формулировка D1
<!-- Дайджест даёт `asserts_without_example: 0`, но D14–D20 появились в спеке
     после подписи (по итогам находок), а формулировка D1 исправлена по
     результату теста. Подпись настоящая, а не n/a. -->
**CI run:** прогон на 1574202 зелёный по gates и tests; шаг delivery зеленеет этим коммитом
**Commit:** 1574202

## Прогон в чистом клоне

```
$ git clone . <clone> && cd <clone>
$ python3 scripts/delivery_check.py   → 0 errors, 0 warnings
$ python3 -m pytest -q                → 200 passed, 1 skipped
```

## Shape oracles
- [x] PASS — `pre-commit run --all-files`: 27 хуков, упавших 0
- [x] PASS — `ruff` / `ruff format --check` / `mypy --strict` чисты
- [x] PASS — гейты просматривают непустое число файлов

## Behavior oracles
- [x] PASS — `pytest`: 200 тестов, 1 пропущен (разрушающий цикл миграций — в CI)
- [x] PASS — покрытие ядра **94 %** при пороге 80 %
- [x] PASS — примеры D1–D20 закрыты тестами, `asserts_without_example: 0`
- [x] PASS — классификация не делает сетевых запросов: `httpx` в тестах падающий

## Product oracles
- [x] PASS — `eval-smoke.md` прогнан: распределение по группам и объяснение по домену
- [ ] n/a — `delivery/evals/smoke/` пуст: устойчивый набор заводится в Ф5

## Три находки о методе, а не о коде

Все три вынесены в спеку и адресованы калибровке Ф8 — с числами, чтобы
разговор с заказчиком шёл на них.

1. **Окно усреднения защищает от выбросов слабее, чем заявлено.** Месяц с
   удвоением на плоской серии даёт +50 % при окне 2, +25 % при окне 4 и
   +16,7 % при окне 6 — выше порога «средних» (+10 %) при любом практичном
   окне. Плоский проект с одним аномальным месяцем становится «средним».
   Лекарство — медиана вместо среднего, но это смена метода, заданного ТЗ.
2. **Форма `weak_growth` стоит ровно на пороге.** Шесть доменов из двенадцати
   ниже +10 %, шесть выше: группа определяется шумом ±3 %. В строгой
   golden-таблице сценария нет — вместо ожидания стоит тест, стерегущий
   разброс. Удобное ожидание сделало бы таблицу зелёной по случайности.
3. **Конфликт в самих порогах ТЗ.** Если требовать подтверждающую метрику и
   для «средних», проект с ростом трафика +80 % без ссылочного не попадает ни
   в одну группу: «хорошие» не пускают, «средние» тоже, а определение
   «плохих» (< +10 % или падение) к нему не подходит. До решения заказчика
   `medium.supporting_required: 0`, конфликт описан прямо в сиде порогов.

## Что нашли тесты в самой реализации

- **Информационные записи валили решение.** При `supporting_required: 0`
  запись «топ-10 вырос на 12 % при ориентире 15 %» считалась провалом
  условия, которого никто не требовал, и `weak_growth` уходил в `poor`.
  Введено различение решающих условий и объяснительных фактов.
- **Ожидание D1 в спеке было моим и неверным.** Тест показал фактическое
  поведение; в спеке теперь оно, а не удобное.
- **`late_drop` — это `poor`.** По точкам А→Б проект ниже старта на 28 %;
  ожидание `medium` в таблице тоже пришлось исправить по факту.
- **«Хороших» не бывает без шага 2 воронки** (D18): подтверждающие метрики
  приходят только там. Свойство конвейера, теперь под тестом.

## Ревью рисковых мест

**По классам риска.**

- **Деньги.** Прямого расхода здесь нет: `classify_project` и `classify_all`
  не касаются провайдера, и это проверяется падающим `httpx` в тестах. Косвенно
  деньги затронуты сильнее, чем в Ф2: неверная группа отправит в кейс проект,
  которого там быть не должно, и это дороже лишнего запроса. Защита —
  golden-таблица и объяснение в `Reason`, по которому решение проверяет человек.
- **Безопасность.** Риска нет: поставка не добавляет входов извне, не трогает
  аутентификацию и не пишет ничего, кроме `Verdict` и `Ruleset`. Пороги
  приходят из базы, а не из пользовательского ввода; когда появится экран
  Ф6, проверку прав на запись `Ruleset` придётся ставить там.
- **Транзакция БД.** `classify_projects` делает `session.flush` и **не**
  вызывает `commit` — в отличие от `collect_projects`, который коммитит по
  ходу чекпойнтами. Разница сознательная: классификация быстрая и целиком
  помещается в транзакцию вызывающего, частичный результат здесь бессмыслен,
  а `_store` идёт через `insert(...).on_conflict_do_update`, то есть повтор в
  одной транзакции не даёт дублей. Риск в другом: вызывающий, забывший
  `commit`, получит молча потерянные вердикты — в CLI `commit` стоит явно, в
  Ф5 это ляжет на обработчик.
- **Производительность.** `load_series` — один запрос на проект; при сотне
  проектов это сотня round-trip'ов, как и в `funnel`. На масштабе ТЗ
  приемлемо, но с экраном Ф6 и пересчётом всей базы (Ф3б) переписывается в
  один запрос с группировкой. Место названо, чтобы не искать заново.
- **Новый модуль.** `classify/thresholds.py`, `rules.py`, `points.py`,
  `deltas.py`, `series.py`, `rulesets.py`, `verdicts.py` — у них ещё нет ни
  одного читателя, кроме тестов. Самое хрупкое место — `rules._satisfied`:
  от флага `decisive` зависит группа, и ошибка в нём выглядит как «правила
  неверны», а не как «условие не туда отнесено».

## Spec coverage gaps
- Нормализация на длительность работ — Ф3б, ждёт формулу заказчика.
- Пересчёт по смене версии порогов и предпросмотр «кто сменит группу» — Ф3б.
- Диагностика «плохих» — Ф3б.
- Волна В2 (③ OKF) — после Ф3 целиком, отдельной сессией.

## Объём и новое правило

`circuit breaker: net loc_diff 1584 > 800` — второе срабатывание подряд, и на
этот раз фаза резалась **заранее**. Значит дело не в конкретной поставке:
половина фазы всё равно не влезает в порог, а больше половины диффа — тесты.

Решение принято человеком: порог 800 остаётся, а фазы режутся мельче — на
поставки по два-три модуля. Правило записано в `AGENTS.md` и применяется со
следующей поставки; для этой стоит waiver, потому что она написана до его
принятия.

## Verdict
- [x] READY FOR HANDOFF
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

Поставил Verifier `human:anthony`, 2026-09-10, вместе с waiver по объёму.

Принято с четырьмя объявленными пробелами: нормализация на длительность,
пересчёт по версии порогов, предпросмотр смены группы и диагностика «плохих»
— всё это Ф3б. Три находки о методе адресованы калибровке Ф8.
## Assertion digest (ревью ожиданий, не кода)

База: `eb0a70c` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **55**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
D13	assert group is expected, (
D14	assert groups <= {Group.MEDIUM, Group.POOR}
D14	assert len(groups) == 2, "разброс исчез — форма или порог изменились, проверьте калибровку"
D15	assert pct is not None
D15	assert pct.pct is not None
D15	assert 10.5 < pct.pct < 11.6, f"ожидали ~11,3 % вместо 12 %, получили {pct.pct:.2f} %"
D13	assert _decide(series, thresholds, _period_start(series)) is Group.GOOD
D13	assert _decide(series, strict, _period_start(series)) is not Group.GOOD
D13	assert SHAPES[ScenarioName.STEADY_GROWTH].traffic_growth == 2.6
D13	assert SHAPES[ScenarioName.WEAK_GROWTH].traffic_growth == 1.12
D13	assert SHAPES[ScenarioName.DECLINE].traffic_growth == 0.68
D13	assert SHAPES[ScenarioName.BACKLINK_SPIKE].refdomains_growth == 3.4
D1	assert windowed is not None
D1	assert windowed.pct == pytest.approx(50.0), "окно обязано делить выброс пополам"
D1	assert _decide(_series(flat)).group is Group.POOR
D1	assert _decide(_series(spiked)).group is Group.MEDIUM, "ограничение метода, а не сюрприз"
D1	assert delta is not None
D1	assert delta.pct == pytest.approx(expected_pct, abs=0.1)
D1	assert _decide(spiked, thresholds).group is Group.MEDIUM
D3	assert decision.group is Group.MEDIUM
D5	assert decision.group is Group.MEDIUM
D6	assert decision.group is Group.INSUFFICIENT_DATA
D6	assert any(reason.subject == "months_after_start" for reason in decision.reasons)
D7	assert decision.group is Group.MEDIUM
D7	assert supporting.passed is False
D8	assert decision.group is Group.MEDIUM
D8	assert traffic_pct.passed is False
D9	assert decision.group is Group.INSUFFICIENT_DATA
D9	assert gap.fact == 3
D10	assert decision.reasons
D10	assert reason.subject
D10	assert isinstance(reason.passed, bool)
D10	assert reason.note
D10	assert {"subject", "fact", "threshold", "passed", "note", "decisive"} <= set(payload[0])
D11	assert ranked[0] is big_absolute
D16	assert _decide(series, thresholds).group is _decide(series, heavy).group
D4	assert decision.group is Group.POOR
D17	assert decision.group in {Group.POOR, Group.MEDIUM, Group.INSUFFICIENT_DATA}
D18	assert decision.group is Group.MEDIUM
D18	assert supporting.fact == 0
D19	assert first.id == second.id
D19	assert count == 1
D19	assert first.is_active is True
D19	assert thresholds_of(active).good.org_traffic.growth_pct_min == 50
D12	assert verdict.ruleset_id == ruleset.id
D12	assert verdict.group is decision.group
D12	assert verdict.reasons["checks"]
D12	assert len(verdicts) == 2
D12	assert lenient_decision.group is Group.GOOD
D12	assert strict_decision.group is not Group.GOOD
D20	assert report.total == 3
D20	assert sum(report.by_group.values()) == 3
D20	assert report.ruleset_version == "0.1.0-draft"
D20	assert projects[0].status is ProjectStatus.CLASSIFIED
D12	assert count == 1
```

✅ **Каждое утверждение ведёт к примеру спеки** (D1 D10 D11 D12 D13 D14 D15 D16 D17 D18 D19 D20 D3 D4 D5 D6 D7 D8 D9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base eb0a70c -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 12 code (+3 process docs) / +1607/-23 (net +1584) |
| commits | 4 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_classify_golden.py (новый оракул), tests/test_classify_rules.py (новый оракул), tests/test_classify_verdicts.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
