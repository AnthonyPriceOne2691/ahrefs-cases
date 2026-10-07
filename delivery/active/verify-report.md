# Verify report: rows-remember-country

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M81 (repro) | `tests/test_rows_country.py` | **до правки** красный: кампания по DE получила 10 месяцев, купленных по US; после — 0, кампания по US получает свои, как прежде |
| M79, M82–M86 | `tests/test_rows_country.py` (сбор фикстурным провайдером, приём, обработчик карточки, лист и текст кейса) | 8 passed |
| M80 | `tests/test_migrations.py` на временной базе (`MIGRATION_CYCLE_TEST=1`) | 5 passed с прежними: точкам проставлены `US` и пустая строка, откат убирает колонку; модели и миграции сходятся |
| M87 | `web/src/pages/__tests__/intake.test.tsx` | 24 passed |
| Мутанты | без фильтра страны в переносе месяцев; оговорка всегда пуста | M81 красный; оба теста M84 красные; код возвращён |
| Полный сьют | `pytest` | 871 passed, 12 skipped, один красный: `test_second_campaign_does_not_buy_the_same_months_again` клал «купленные» точки кампании по US без страны, то есть как купленные по всему миру. Данные трёх тестов переноса приведены к покупке (`country="US"`) — «давняя кампания» и «другой режим» без этого проходили по неверной причине; `tests/test_collect_cache.py` — 16 passed |
| Фронт целиком | vitest, `tsc`, ESLint | 23 файла, 235 passed; чисто |
| Живой проход | стенд: миграция на копии базы, API и воркер на коде ветки, Chrome по CDP | см. ниже |

## Исполнение рисковых путей

- Миграция `e2f3a4b5c6d7` — прогнал `alembic upgrade head` на копии базы стенда (`cases_geo`), увидел:
  колонка добавлена, точкам проставлены страны их проектов (US 2669, GB 1929, DE 1219…), `/api/health`
  отвечает новой головой. at=2026-10-07
- Приём со сменой страны — загрузил на стенде кнопкой «Загрузить файл» строку `zapier.com` (ряды US) с
  гео DE, увидел: «Принято с замечаниями», «2 · geo · первая страна сменилась — цифры остаются по прежней,
  пока ряды не купят заново · США (US) → Германия (DE)»; смета цикла — 0 units (ряды не докупаются). at=2026-10-07

## Что нашёл живой проход

- **Пояснение над замечаниями врало для смены страны:** «ячейку разобрать не удалось — она не записана»
  стоял над любым замечанием, а гео разобрано и записано. Теперь у неразобранных ячеек — прежний текст, у
  смены страны — свой; M87 это проверяет.
- **Замечание сравнивало старую страну с новой:** возврат к стране, по которой ряды куплены (DE → US при
  рядах US), тоже давал «цифры остаются по прежней», хотя теперь они по первой стране. Сравнивается страна
  рядов с новой первой страной; M83 — с возвратом. На стенде: после возврата к US в карточке оговорки нет,
  после DE — «цифры Ahrefs куплены по стране США (US) — до того, как первой страной проекта стала Германия
  (DE)»; в PDF-брифе (`render`) — в строке «ГЕО» и в тексте листа «Динамика».

## Ревью рисковых мест

**Миграция.** `op.add_column("metric_points", sa.Column("country", sa.String(2), nullable=False,
server_default=""))` и проставление `split_part(project.geo, ',', 1)`; «весь мир» — пусто. Откат —
`op.drop_column("metric_points", "country")`, данные проекта не трогаются.

**Деньги.** Покупка не меняется: страны нет в ключе `uq_metric_point_identity`, смена страны рядов не
докупает (смета цикла на стенде — 0 units). Сужен только бесплатный перенос месяцев между кампаниями:
`MetricPoint.country == ahrefs_country(project.geo)` — кампания другой страны теперь покупает свои
месяцы, и это правильная цена её цифр. Реестр плана тем же ключом: `ahrefs_country(project.geo)` в `key`.

**Транзакция БД.** Запись страны идёт тем же `INSERT … ON CONFLICT DO UPDATE` в транзакции сбора;
замечание приёма — одним запросом стран рядов на весь список (`_bought_countries`), без записи.

**Безопасность.** Риска нет, потому что новых входов и прав нет: `geo_note` — поле прежней карточки под
`require_right("read")`, замечание — в отчёте того же запроса приёма. Текст оговорки и замечания собирается из
справочника стран (`storage/geo._name`) по проверенным кодам (`parse_geo`), а не из сырого ввода файла.

**Интеграция.** Запрос к Ahrefs не меняется: страна запроса та же — `country=ahrefs_country(project.geo)` в
`HistoryRequest`, — она теперь только запоминается у точки (`country=item.task.request.country`). Меняется
лишь, какие месяцы план заказывает у кампании другой страны: раньше он отдавал их ей из чужой страны бесплатно,
теперь заказывает её собственные.

**Ошибки.** Риска нет, потому что новых отказов нет: замечание не останавливает строку, оговорка — `None`,
когда всё по первой стране.

**Производительность.** `bought_countries` — `SELECT DISTINCT country` по одному проекту и источнику на
карточку и на кейс; приём — один запрос на весь список.

## Чего проверка НЕ доказывает

- Прод: проставленные миграцией страны на боевой базе — проверка после выкатки (`observe_signal`).
- Проекты, у которых до сегодняшних списков стран (#45) гео менялось вручную в базе, получат страну
  нынешнего проекта, а не ту, по которой ряды куплены, — таких на проде не встречено.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **29**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M80	assert rows == [("us.rows.migration.example", "US"), ("world.rows.migration.example", "")]
M80	assert column == []
M81	assert to_de == 0, "кампания по DE получила месяцы, купленные по US"
M81	assert to_us > 0
M79	assert await _countries(db_session, several) == ("DE",)
M79	assert await _countries(db_session, world) == ("",)
M82	assert told == [(2, "geo", "geo_changed", "США (US) → Германия (DE)")]
M82	assert report.accepted == 1
M82	assert (await _project(db_session, SITE)).geo == "DE"
M83	assert first.notices == ()
M83	assert [item.detail for item in moved.notices] == ["США (US) → Германия (DE)"]
M83	assert back.notices == ()
M84	assert after_change.geo_note == NOTE
M84	assert mixed.geo_note == "часть " + NOTE.replace("цифры Ahrefs куплены", "цифр Ahrefs куплена")
M84	assert own.geo_note is None
M84	assert rows_note("WW", ["US"]) == (
M84	assert rows_note("DE", [""]) == (
M84	assert rows_note("DE", ["US", "CA"]) == (
M84	assert rows_note("DE,AT", ["DE"]) is None
M85	assert rows["ГЕО"] == f"Германия (DE), Австрия (AT); {NOTE}"
M85	assert NOTE in text
M85	assert "по первой из них" not in text
M85	assert "по первой из них" in compose(replace(case, geo_note=None))
M86	assert await _countries(db_session, project) == ("DE",)
M86	assert rows_note(project.geo, await _countries(db_session, project)) is None
M87	expect(
M87	expect(screen.getByText('США (US) → Германия (DE)')).toBeInTheDocument();
M87	expect(screen.getByTestId('geo-note')).toHaveTextContent('цифры Ahrefs остаются по прежней');
M87	expect(screen.queryByTestId('notices-note')).not.toBeInTheDocument();
```

✅ **Каждое утверждение ведёт к примеру спеки** (M79 M80 M81 M82 M83 M84 M85 M86 M87), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 23 code (+20 process docs) / +599/-32 (net +567) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_rows_country.py (новый оракул) |
| implement_retries | 2 — живой проход на стенде: пояснение над замечаниями говорило «ячейку разобрать не удалось» и для смены страны; замечание сравнивало старую страну с новой и ложно срабатывало при возврате к стране рядов |
| verify_fails_before_green | 1 — полный сьют: `test_second_campaign_does_not_buy_the_same_months_again` клал «купленные» точки без страны; плюс гейт длины файла: `collect/plan.py` 506 > 500 строк — ключ плана свёрнут в строку |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
