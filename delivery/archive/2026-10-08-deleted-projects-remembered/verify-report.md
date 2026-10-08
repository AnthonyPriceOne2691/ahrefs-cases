# Verify report: deleted-projects-remembered

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M105 (repro) | `tests/test_deleted_projects.py` — сбор фикстурой, удаление `delete_rows`, новая загрузка | **до правки** красный: пустой домен спрошен снова; после — не спрашивается |
| M106 | то же, две живые кампании | вторую кампанию сбор спрашивает — и до, и после |
| M107 | `tests/test_deleted_projects.py` — покупка удалённого проекта и живого другого сайта | до правки красный (`refdomains` у нового); после — пусто у нового, `refdomains` у живого |
| M108 | `tests/test_api_projects_delete.py` — удаление обеих кампаний `gone` через API | до правки красный (одна судьба на 50); после — две по 40 и 10 |
| M109 | то же — консоль держит `claim_start`, удаление из второго потока | удаление ждёт, затем 409 «прогон N»; проект цел — и до, и после (окно закрыто #58) |
| Прежние тесты | `tests/test_collect_run.py` (память), `tests/test_purchases_explain_the_dash.py` (E1–E4) | после правки сигнатуры `empty_since` и уточнения правила покупок — зелёные |
| Миграция | `tests/test_migrations.py` на временной базе `cases_migtest` | 3 passed: вверх, вниз, вверх; модели и миграции сходятся |
| Полный сьют | `pytest` на восстановленной дев-базе | 895 passed, 12 skipped |
| Живой проход | стенд: миграция на копии `cases_geo`, API и воркер на коде ветки, Chrome по CDP | см. ниже |

## Исполнение рисковых путей

- Миграция `f3a4b5c6d7e8` — накатил на копию стенда `cases_geo`, увидел: у всех 850 строк журнала `project_ref`
  проставлен из `project_id`. at=2026-10-08
- Удаление кампаний и журнал — на стенде открыл карточки обеих кампаний `nordvpn.com` (13039, 13040), нажал
  «Удалить проект» → «Да, удалить»; открыл журнал с фильтром дат 15.09.2026, раскрыл прогон №1088 (тот, где
  находка видела «ok, 264»), увидел: «без замечаний собрано: 57, из них проектов удалено: 2»; API — две судьбы
  `nordvpn.com` «ok, 132», обе удалены. at=2026-10-08

## Что нашла проверка

- **Инцидент: тест цикла миграций стёр дев-базу.** `MIGRATION_CYCLE_TEST=1` без своего `DATABASE_URL` прогнал
  цикл «вверх, вниз до пустой схемы, вверх» по дев-базе `cases`. Восстановлена копией стенда `cases_geo`
  (75 проектов); стёртая отложена как `cases_wiped_20261008`. Потеряны две кампании `nordvpn.com` — их час назад
  удалил проход M108 на стенде. С этой поставки цикл требует имя разрушаемой базы
  (`MIGRATION_CYCLE_TEST=<имя>`) и на чужой базе отказывает громко; в CI — `cases`.
- **«Только покупки живых» — слишком широко:** строки расхода без строк журнала (тесты E2, E3, пробы) перестали
  считаться. Правило сужено: не считается покупка, чей прогон знал домен только у удалённых проектов.

## Ревью рисковых мест

**Миграция.** `op.add_column("run_items", sa.Column("project_ref", sa.Integer(), nullable=True))` и
`UPDATE run_items SET project_ref = project_id WHERE project_id IS NOT NULL`; откат —
`op.drop_column("run_items", "project_ref")`. Колонка без внешнего ключа и без индекса: читается только в
свёртке судеб одного прогона.

**Деньги.** Память о пустом домене расширена только на строки удалённых проектов того же домена:
`and_(RunItem.project_id.is_(None), RunItem.raw_domain == project.domain)` — пустота не покупается заново после
удаления; живые кампании ею не делятся (M106), так что лишних пропусков у кампании с данными нет.

**Транзакция БД.** Риска нет, потому что удаление по-прежнему берёт `hold_start` до проверки идущей работы, а
консоль держит тот же замок до коммита строки прогона — M109 проверяет это двумя соединениями.

**Безопасность.** Риска нет, потому что новых входов и прав нет: удаление — под прежним `delete_projects`,
`project_ref` — номер строки, которой больше нет, без данных проекта.

**Ошибки.** Риска нет, потому что у строк журнала старше колонки `project_ref` пуст, и ключ судьбы падает на
домен, как прежде (`item.project_ref if item.project_ref is not None else item.raw_domain`).

**Производительность.** Риска нет, потому что память о пустом домене — тот же запрос последних строк проекта
с условием `or_(…)` (строк журнала у проекта единицы, `limit` — число подтверждений), а «что покупали» — два
коррелированных `EXISTS` на строку расхода одного домена, у карточки одного проекта.

## Чего проверка НЕ доказывает

- Прод: строк журнала удалённых проектов с номером там нет, пока кто-то не удалит проект после выкатки.
- Кампании `nordvpn.com` дев-базы не вернуть: в обеих базах их больше нет.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

Два утверждения `tests/test_collect_run.py` (`empty_since(db_session, project)`) — прежние, пример Y5 той
поставки: изменён только аргумент под новую подпись; дайджест привязал их к M109, перенеся номер из соседнего
файла — в этом файле изменённых строк с номером нет.

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **12**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M108	assert client.delete(f"/api/projects/{project}", headers=headers).status_code == 200
M108	assert fates == [(GONE, 10, True), (GONE, 40, True)]
M109	assert waited, "удаление прошло мимо замка, который держала консоль"
M109	assert refused.status_code == 409
M109	assert f"прогон {run_id}" in refused.json()["detail"]
M109	assert writer(lambda s: _rows(s, stand.keeper))[0]["projects"] == 1
M109	assert await empty_since(db_session, project) == real_checks[-1]
M109	assert await empty_since(db_session, project) == checked
M105	assert again.calls == []
M106	assert again.calls == [EMPTY]
M107	assert await bought_metrics(db_session, "rebought.example.com") == frozenset()
M107	assert Metric.REFDOMAINS in (await bought_metrics(db_session, "alive.example.com") or ())
```

✅ **Каждое утверждение ведёт к примеру спеки** (M105 M106 M107 M108 M109), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 12 code (+18 process docs) / +335/-29 (net +306) |
| commits | 3 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — .github/workflows/quality.yml, tests/test_deleted_projects.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.

