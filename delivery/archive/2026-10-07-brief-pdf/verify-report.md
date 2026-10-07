# Verify report: brief-pdf

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M33, M35, M37 | `tests/test_brief_sheet.py` | 6 passed |
| M34, M36 | `tests/test_cases_pdf.py`, `tests/test_cases_charts.py`, `tests/test_cases_builder.py` | 59 passed вместе с прежними проверками листа |
| Лист глазами | рендер кейса под NDA с брифом и двумя странами, страницы WeasyPrint по одной → PNG | стр. 1–2 — бриф: шапка «Бриф для копирайтера», клиент, страны, период; «Непубличный проект (NDA)…»; разделы шаблона, «заполняет специалист» у пустых; ссылки «Обзор / Органические ключевые слова / Ссылающиеся домены» по Германии и Австрии; стр. 3 — лист «Динамика» |
| Живой проход | стенд на копии дев-базы (API и воркер на коде ветки), Chrome по CDP | «Загрузить файл» → «Запустить» → прогон №2330 «цикл по файлу — готов, собрано 2 кейса», «Скачать 2 кейса»; в карточке `brief-ok.example.com` «Скачать PDF» отдал «brief-ok.example.com — Кейс v1.pdf» на три страницы: бриф с NDA, пункты из файла (тематика, тип сайта, запрос клиента, сложность) и из карточки (отдел, вид проекта, цели, трудности) |

## Исполнение рисковых путей

- `templates/case.html.j2` — прогнал `render_html` + WeasyPrint на кейсе под NDA с брифом и `DE,AT`,
  разрезал документ по страницам (`Document.copy`) и перевёл каждую в PNG через `sips`, увидел: бриф на
  двух страницах без наездов и обрывов строк, лист «Динамика» — третья, целиком. Затем на стенде
  собрал PDF циклом по файлу через интерфейс и скачал кнопкой карточки — те же три страницы. at=2026-10-07

## Ревью рисковых мест

**Безопасность — риска нет**, потому что ссылки на отчёты собирает `report_links` из домена, режима и
кодов стран через `urlencode` с `quote`, а значение пункта-ссылки на листе — только то, что прошло
`normalize` (https на Google Drive); шаблон выводит всё с автоэкранированием. `<a href>` WeasyPrint не
загружает — запрет сети в `_DenyNetwork` прежний.

**Интеграция.** Формат адресов `app.ahrefs.com/site-explorer/…` взят из настоящих ссылок интерфейса,
документации Ahrefs на него нет: если Ahrefs сменит параметры, ссылка откроет отчёт без периода или
страны, а не сломает лист. Поэтому лист говорит «проверьте период в отчёте», а `observe_signal` — проверка
одной ссылки владельцем.

**Производительность — риска нет**, потому что раскладка листа — 31 строка на кейс из словаря
`_AUTO` и `FIELDS_BY_KEY`, а ссылки — три на страну.

**Новые модули.** `export/brief_sheet.py` — раскладка и подстановки; `export/ahrefs_links.py` — ссылки.

## Чего проверка НЕ доказывает

- Что ссылки открывают в Ahrefs именно нужный отчёт с нужным периодом: агент в интерфейс Ahrefs не
  ходит — проверка одной ссылки владельцем после выкатки.
- Подписи «домен скрыт» на экранах кейсов и проектов ещё прежние — поставка 3б, до выкатки.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **38**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M33	assert printed_fields() == {field.key for field in FIELDS}
M33	assert tuple(section.title for section in brief_sections(_case())) == SECTIONS
M33	assert rows["Кто из сотрудников вёл проект"] == "Пётр"
M33	assert rows["Услуга (по которой пишем кейс)"] == "SEO-продвижение"
M33	assert rows["Период сотрудничества"] == "10.2024 — 09.2025 (12 мес.)"
M33	assert rows["ГЕО"] == "Германия (DE)"
M33	assert rows["Процент роста показателей"] == "органический трафик +160 %"
M33	assert rows["Тематика"] == "путешествия"
M33	assert rows["Бюджет проекта / объём работ"] == "120 (объём работ из файла)"
M33	assert rows["Тип сайта"] == "Маркетплейс"
M33	assert rows["Поставленные цели"] == "топ-10 по турам"
M33	assert rows["Трудности, которые возникли"] == ""
M33	assert EMPTY in render_html(_case())
M35	assert [link.country for link in links] == ["Германия (DE)"] * 3 + ["Австрия (AT)"] * 3
M35	assert urlsplit(links[0].url).path == "/site-explorer/overview"
M35	assert overview["target"] == ["tours.example/"]
M35	assert overview["mode"] == ["subdomains"]
M35	assert overview["country"] == ["de"]
M35	assert overview["chartInterval"] == ["2024-07-01|2025-09-01"]
M35	assert keywords["country"] == ["at"]
M35	assert "chartInterval" not in parse_qs(urlsplit(links[2].url).query)
M35	assert [link.country for link in links] == ["Весь мир"] * 3
M35	assert parse_qs(urlsplit(links[0].url).query)["country"] == ["all"]
M35	assert parse_qs(urlsplit(links[1].url).query)["country"] == ["allByLocation"]
M35	assert f'href="{links[0].url.replace("&", "&amp;")}"' in render_html(_case(geo="WW"))
M37	assert check(case)
M37	assert not list(tmp_path.iterdir())
M34	assert case.title == "example.com"
M34	assert case.domain == "example.com"
M34	assert build_case(_project(), verdict, {}).anonymized is False
E9	assert sheet_pages(html) == 1
E9	assert rendered.pages > 1, "бриф идёт перед листом, документ не одностраничный"
M36	assert rendered.pages > 1
M36	assert sheet_pages(render_html(_case())) == 1
M34	assert NDA_WARNING in closed
M34	assert "example.com" in closed
M34	assert NDA_WARNING not in open_
M7	assert sheet_pages(six) == 1
```

✅ **Каждое утверждение ведёт к примеру спеки** (E9 M33 M34 M35 M36 M37 M7), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 13 code (+17 process docs) / +585/-58 (net +527) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/sheet_pages.py (новый оракул), tests/test_brief_sheet.py (новый оракул) |
| implement_retries | 2 — 12 тестов листа и сборки (одна страница, анонимность, режим проекта в памяти); mypy на переиспользованном имени в `brief_sheet._row` |
| verify_fails_before_green | 1 — проверка ссылок всего мира сравнивала другой период |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
