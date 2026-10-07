# Verify report: screenshots-pdf

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M54–M59 | `tests/test_brief_screens.py` (свой проект в сессии с откатом, каталог скринов подменён) | 13 passed |
| Сброс умолчания Pillow — настоящий оракул | мутант: строка `ImageFile.LOAD_TRUNCATED_IMAGES = False` заменена на `pass` | 3 красных: `cut-jpeg` (M56), M59 PNG и JPEG; строка возвращена |
| Прежний PDF и загрузка скринов | `tests/test_cases_pdf.py`, `tests/test_storage_screenshots.py`, `tests/test_api_screenshots.py` | зелёные |
| Слои | `lint-imports` | 2 kept, 0 broken |
| Живой проход | стенд (API и один воркер RQ на коде ветки), Chrome по CDP: файл списка на «Прогонах» → «Запустить» → «Скачать PDF» в карточке | цикл 2345 с обрезанным пополам файлом ИИ-скрина: PDF на 3 страницы, на листе один скрин Ahrefs, строка «1 шт. — в разделе «Скрины» ниже», в журнале воркера `screenshot_damaged_for_case project_id=24151 screenshot_id=3`; файл возвращён, цикл 2350: 4 страницы, два скрина с подписями «Отчёт Ahrefs · …» и «Видимость в ИИ · …», строка «1 шт. — в разделе «Скрины» ниже; там же видимость в ИИ — 1 шт.», «Динамика» — одна последняя страница, PDF 724 КБ |

## Исполнение рисковых путей

- `src/ahrefs_cases/export/pdf_renderer.py` — прогнал `node step12.mjs` (Chrome по CDP: файл списка на экране
  «Прогоны», «Запустить», сборка кейса в воркере RQ стенда, «Скачать PDF» в карточке) дважды: с обрезанным
  пополам PNG на диске и с целым. Увидел: в воркере — процессе, где WeasyPrint импортирован, — обрезанный PNG
  отвергнут проверкой и пропущен с записью `screenshot_damaged_for_case`, а не дорисован серым; целые PNG
  прошли загрузчик рендера и стоят на листе с подписями. Растеризовал страницы PDFKit и посмотрел глазами.
  at=2026-10-07

## Ревью рисковых мест

**Безопасность.** Загрузчик рендера по-прежнему не ходит ни в сеть, ни на диск: пропускается только
`data:` из `STORED`, и байты сначала проходят `ensure_intact(content, mime)`. Подпись скрина вводит
человек — Jinja экранирует её (`select_autoescape(default_for_string=True, default=True)` действует и на
`case.html.j2`; проба: подпись `<img src="https://…">` легла на лист текстом и в `alt`, и в подписи), а
контент-запрет её читает: `hits.extend(_scan("подпись скрина", image.caption))`.

**Глобальное состояние процесса.** `ImageFile.LOAD_TRUNCATED_IMAGES = False` в `pdf_renderer` меняет
Pillow на весь процесс — так же, как WeasyPrint менял его до нас; импортирует WeasyPrint только этот
модуль, и флаг ставится один раз при импорте, рендер его не трогает (проверено: после `render()` значение
прежнее). Для рендера разницы нет: обрезанную картинку наш загрузчик не пускает раньше, чем её увидит
WeasyPrint.

**Ошибки и журнал.** Отказ рендера берёт текст причины: `raise reason from reason.__cause__` — без
`FatalURLFetchingError`, который несёт адрес целиком, в цепочке. Пропуск файла — `logger.warning` с
`project_id`, `screenshot_id` и причиной; пустого `except` нет.

**Производительность.** Чтение и полная распаковка — в потоке: `content = await
anyio.to_thread.run_sync(_intact, folder, row.storage_key, row.mime)`. Картинка распаковывается дважды
(здесь и в загрузчике рендера) — на 2000 px это десятки миллисекунд. PDF растёт на вес скринов: 2 скрина
≈ 620 КБ дали PDF 724 КБ; HTML несёт их base64 (×1,33) в памяти воркера.

**Деньги.** Риска нет, потому что `load_screens` в `builder._attempt` стоит после сверки вердикта с
рядами и только читает строки скринов и файлы с диска: запросов к Ahrefs и расхода units у него нет, а
смета и ступень кейса не тронуты.

**Транзакция БД.** Сборка скринов только читает (`select … order_by(ProjectScreenshot.id)`) в сессии
сборки кейса; записей нет.

## Чего проверка НЕ доказывает

- Проект с 30 скринами по 1,5 МБ (PDF ~45 МБ, память воркера) не собирался — на стенде два скрина.
- Порча **внутри** данных JPEG (не обрезка) контрольной суммы не имеет и распакуется мусором; наши файлы
  пишутся атомарно (`save`: временный файл и переименование), так что это порча диска, а не записи.
- Экрана загрузки скринов ещё нет — следующий PR; на стенде скрины загружены через API.
- Прод не проверен — выкатка по слову владельца.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **14**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M54	assert 'src="data:image/png;base64,' in html
M54	assert "Отчёт Ahrefs · Обзор · Германия (DE)" in html
M54	assert _told(_case(SHOT)) == "1 шт. — в разделе «Скрины» ниже"
M54	assert _told(_case(SHOT, ai)).endswith("ниже; там же видимость в ИИ — 1 шт.")
M54	assert _told(_case()).startswith("ещё не загружены")
M54	assert _told(_case(ai)).endswith("видимость в ИИ — 1 шт. в разделе «Скрины» ниже")
M55	assert rendered.path.read_bytes()[:5] == b"%PDF-"
M55	assert sheet_pages(render_html(case)) == 1
M56	assert (
M56	assert not list(tmp_path.iterdir())
M57	assert [image.caption for image in images] == ["есть"]
M57	assert images[0].content == prepared.content
M57	assert told == ["screenshot_missing_for_case", "screenshot_damaged_for_case"]
M58	assert [hit.where for hit in hits] == ["подпись скрина"]
```

✅ **Каждое утверждение ведёт к примеру спеки** (M54 M55 M56 M57 M58), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 11 code (+19 process docs) / +395/-13 (net +382) |
| commits | 1 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 commit(s) after first phase: handoff |
| harness_hardened | yes — tests/test_brief_screens.py (новый оракул) |
| implement_retries | 2 — `verify` Pillow бросает `SyntaxError` мимо `(ValueError, OSError)`, а текст отказа WeasyPrint нёс base64 целиком; обрезанный JPEG проходил распаковку из-за флага, который WeasyPrint ставит при импорте |
| verify_fails_before_green | 2 — `cut-jpeg` красный дважды: сперва срез длиннее самого файла, затем флаг `LOAD_TRUNCATED_IMAGES` WeasyPrint |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
