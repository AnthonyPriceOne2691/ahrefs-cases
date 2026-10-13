# Verify report: brief-autofill

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M127, M128 (repro) | `tests/test_cases_pdf.py` — шапка «Динамики», `number`/`percent` на половине | **до правки** (исполнитель Б) — 6 красных: в шапке `<span>linkbuilding</span>`; `'CaseData' object has no attribute 'service_label'`; `number(582.5)` — `'582' == '583'`, ячейка таблицы `582`; `percent(2.15)` — `'+2,1 %'` против `'+2,2 %'`; после — зелёные |
| M128 — графики | `tests/test_cases_charts.py::test_point_label_rounds_half_like_the_table` | **на прежнем `charts.py`** — красный (`'>1 001</text>' in svg` — на кривой «1 000»); после — зелёный |
| M129–M134 | `tests/test_brief_known.py` — правило подстановки по фактам | 34 passed: отдел по услуге («Комплекс» — без отдела), тип услуги по периоду (порог 3 мес.), вид проекта по точке А, срез и период 1 (при «по этапам» — нет), весомость по группе, тематика и тип сайта по словарю ниш; заполненный пункт не подменяется |
| M135 | `tests/test_api_project_brief.py::test_prepared_by_is_whoever_saved_the_brief` | пустой — пишется сохранивший; заполнен — не трогается; очищен в правке — пуст; правка одного NDA и одни очистки — подписи нет; журнал называет ключ, не имя |
| M136 | `tests/test_api_project_brief.py` — сличающий тест | карточка (`brief_known`) и лист PDF печатают одни и те же значения по всем пустым пунктам одного проекта (L258) |
| Полный сьют | `pytest` (дев-база) | 949 passed, 12 skipped (8 мин 33 с) |
| Фронт | `vitest`, `tsc --noEmit`, ESLint, Prettier | 257 passed; чисто. M30 карточки: подменный сервер помнит сохранённое — карточка после записи перечитывается |
| Мутации правила | исполнитель А: трафик карточки обнулён в `None`, затем отключена подпись — 6 тестов покраснели, код возвращён | оракулы различают |

## Исполнение рисковых путей

- `src/ahrefs_cases/export/brief_sheet.py`, `templates/case.html.j2` — стенд (база `cases_geo`, провайдер fixture, API и
  воркер на коде ветки): «Пересобрать кейсы» (прогон №2369, 66 собрано из 80), `zooplus.de — Кейс v15.pdf`
  растеризован: отдел «SEO (по услуге из файла)», тип услуги «Ежемесячное продвижение (период 12 мес.)», вид проекта
  «Рост существующего сайта (трафик на старте — 53 995)», тематика «Товары для животных (по нише «зоотовары»)», бюджет
  «150 (объём работ из файла)», срез «Весь период работ (по умолчанию)», период 1 «09.2024 — 08.2025: SEO-продвижение
  (период и услуга из файла)», весомость «Средняя (группа «средний»)»; пустые без вывода — «заполняет специалист»;
  шапка «Динамики» — «Германия (DE) · зоотовары · SEO-продвижение»; бриф — 2 страницы, «Динамика» — 1. Карточки
  zooplus.de, zapier.com и двух проектов стенда отдают те же значения в `brief_known`. at=2026-10-13
- Карточка в Chrome (стенд): пустой бриф — одна строка; записан один пункт — «Кто подготовил: agent-check@local.test»
  (у учётки нет имени — почта), остальные пункты сразу с подстановкой, без перезагрузки; правка откатана. at=2026-10-13

## Что нашла проверка

- **Две копии подписи услуги.** Исполнители написали каждый свою (`CaseData.service_label` и
  `storage.brief.service_label`) — свойство кейса теперь зовёт вторую (L142).
- **Подписи графиков округляли к чётному** — свой `round` в `export/charts.py`; найдено исполнителем Б вне его файлов,
  исправлено при сведении (подписи печатает `cases.format.number`).
- **Правка одного NDA подписывала бриф** — пустой бриф становился непустым и разворачивался на карточке; подпись —
  только за записанный пункт.
- **Карточка не обновляла подстановку после записи** — `BriefForm` клал в кэш только бриф; теперь карточка
  перечитывается (`exact`, графики не трогаются).
- **Словарь ниш:** «автоматизация» (zapier.com) оставалась без тематики — к «ИТ и софт».
- **Округление половины** берётся по записи числа (`Decimal(repr(value))`), а не по двоичному значению: сверка
  исполнителя Б с ICU (Node 24) — 320 000 значений без расхождений; по двоичному — 5 445 расхождений на одном знаке.

## Ревью рисковых мест

**Данные.** Миграций нет. Подстановка не пишется в бриф — считается при сборке и чтении; «Кто подготовил» пишется в
JSONB брифа тем же путём, что правка специалиста, и правится им же.

**Деньги.** Units не тратятся: подстановка — по уже купленным и записанным данным (вердикт, период, файл);
«Пересобрать кейсы» бесплатна.

**Безопасность.** Новых путей нет; запись брифа — под тем же правом `edit_briefs`, имя сохранившего берётся из его
же учётки и в журнал не пишется (инвариант 8).

**Интеграция.** `brief_known` в ответе карточки — то же поле, другие значения; экран показывает их как прежде.

## Чего проверка НЕ доказывает

- Прод: подстановка в PDF после «Пересобрать кейсы» и шрифтом контейнера (DejaVu) — длинные значения с источником
  в скобках переносятся иначе, чем на Mac (L257).
- Правила команды для «Комплекса» и порога «Тип услуги» — умолчания, ответа команды нет.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **77**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M135	assert response.json()["fields"] == signed  # M135
M135	assert _card(client, project_id)["brief"] == signed  # M135
M135	assert _card(client, project_id)["brief"] == {"goals": "топ-10", "prepared_by": CLERK}  # M135
M135	assert response.json()["fields"] == {**other_keys, "prepared_by": CLERK}  # M135
M134	assert _card(client, project_id)["brief_known"] == from_file  # M134
M134	assert known == {**from_file, "budget": "120 (объём работ из файла)"}  # M134
M131	assert card["verdict"]["comparison"][0]["before"] == 2487.0
M131	assert known["project_kind"] == "Рост существующего сайта (трафик на старте — 2\u00a0487)"
M133	assert known["result_weight"] == "Высокая (группа «хороший»)"  # M133
M136	assert project is not None
M136	assert printed == card["brief_known"]
M136	assert set(printed) == {
M136	assert rows["Чей отдел вёл проект"] == "PR"
M136	assert "department" not in card["brief_known"]
M135	assert first.json()["fields"]["prepared_by"] == "Анна Петрова"
M135	assert record.signed == ["prepared_by"]
M135	assert "Анна Петрова" not in str(record.__dict__)
M135	assert kept.json()["fields"]["prepared_by"] == "Иван"
M135	assert "prepared_by" not in cleared.json()["fields"]
M135	assert "prepared_by" not in _card(client, project_id)["brief"]
M135	assert "prepared_by" not in nda_only.json()["fields"]
M135	assert "prepared_by" not in clears_only.json()["fields"]
M129	assert _known(service=service).get("department") == department
M130	assert MONTHLY_FROM_MONTHS == 3
M130	assert _known(period=period)["service_kind"] == kind
M131	assert _known(traffic_start=traffic).get("project_kind") == kind
M132	assert known["dynamics_slice"] == "Весь период работ (по умолчанию)"
M132	assert known["case_period_1"] == whole
M132	assert _known({"dynamics_slice": "whole"})["case_period_1"] == whole
M132	assert "case_period_1" not in _known({"dynamics_slice": "stages"})
M132	assert "case_period_2" not in known
M132	assert _known(service="seo")["case_period_1"].endswith(
M133	assert _known(group=group).get("result_weight") == weight
M134	assert known.get("topic") == topic
M134	assert known.get("site_type") == site_type
M134	assert set(TOPIC_NICHES) == set(topics)
M134	assert set(SITE_NICHES) == set(sites)
M134	assert _known(niche=niche)["topic"] == f"{topics[key]} (по нише «{niche}»)", niche
M134	assert _known(niche=niche)["site_type"] == f"{sites[key]} (по нише «{niche}»)", niche
M134	assert _known(niche=niche)["topic"] == topic
M136	assert set(full) == {
M136	assert set(full) <= printed_fields()
M136	assert full["budget"] == "120 (объём работ из файла)"
M136	assert set(known) == set(full) - set(brief)
M136	assert known["service_kind"] == full["service_kind"]
M134	assert rows["Тематика"] == "Путешествия (по нише «путешествия»)"  # M134
M121	assert known["budget"] == "120 (объём работ из файла)"
M134	assert known["topic"] == "Путешествия (по нише «путешествия»)"  # M134
M136	assert {key: rows[FIELDS_BY_KEY[key].label] for key in known} == known  # M136
M129	assert rows["Чей отдел вёл проект"] == "SEO (по услуге из файла)"  # M129
M130	assert rows["Тип услуги"] == "Ежемесячное продвижение (период 12 мес.)"  # M130
M131	assert rows["Вид проекта"] == "Рост существующего сайта (трафик на старте — 1\u00a0000)"  # M131
M133	assert rows["Весомость результата"] == "Высокая (группа «хороший»)"  # M133
M132	assert rows["Срез динамики"] == "Весь период работ (по умолчанию)"  # M132
M132	assert rows["Период для кейса 1 — какие услуги делали в этот момент"] == period
M132	assert rows["Тип сайта"] == ""
M132	assert rows["Период для кейса 2 — какие услуги делали в этот момент"] == ""
M132	assert rows["Срез динамики"] == "По этапам (до трёх периодов)"
M132	assert rows["Период для кейса 1 — какие услуги делали в этот момент"] == ""
M131	assert rows["Вид проекта"] == ""  # M131
M128	assert ">1\u00a0001</text>" in svg
M128	assert ">1\u00a0451</text>" in svg
M128	assert ">1\u00a0000</text>" not in svg
M127	assert "<span>США (US)</span><span>финансы</span><span>Линкбилдинг</span>" in sheet
M127	assert "linkbuilding" not in sheet
M127	assert case.service_label == label
M127	assert rows["Услуга (по которой пишем кейс)"] == label
M128	assert number(582.5) == "583"
M128	assert number(1500.5) == "1\u00a0501"
M128	assert number(-582.5) == "-583"
M128	assert number(2.5) == "2,5"
M128	assert percent(12.5) == "+13\u00a0%"
M128	assert percent(-12.5) == "-13\u00a0%"
M128	assert percent(2.25) == "+2,3\u00a0%"
M128	assert '<td class="cell-num">583</td>' in sheet
M128	assert percent(2.15) == "+2,2\u00a0%"
M128	assert percent(-2.15) == "-2,2\u00a0%"
```

✅ **Каждое утверждение ведёт к примеру спеки** (M121 M127 M128 M129 M130 M131 M132 M133 M134 M135 M136), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 18 code (+17 process docs) / +879/-85 (net +794) |
| commits | 7 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_brief_known.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
