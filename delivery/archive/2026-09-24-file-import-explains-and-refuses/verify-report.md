# Verify report: file-import-explains-and-refuses

**Date:** 2026-09-24
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36041318681
**Commit:** ba50791359ec969f56f4090e55a0badd10ac9dd5

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| V1–V15: брак файла и таблицы по ссылке — `400`, в базе ничего; брак строк — отчёт | `pytest tests/test_api_intake.py` | 40 passed; **до правки 22 падения по правильной причине**: `assert 200 == 400` у файлов и таблиц без колонок, у одной шапки, у списка на втором листе, у дубля колонки; `assert 500 == 400` у PDF, CSV и DOCX под именем `.xlsx`, у обрезанной книги и у длинной двоичной строки в `.csv`; «пустое тело запроса» вместо «файл пуст» |
| V21: CLI на списке без колонок — код 2 | `pytest tests/test_cli_exit_codes.py -k unfit` | passed; до правки `assert 1 == 2` |
| B15 под новую границу, пустая первая строка | `pytest tests/test_intake_validate.py tests/test_intake_accept.py` | passed |
| V19: данные подсказки = константы приёма | `pytest tests/test_intake_list_format.py` | 4 passed; реляционный — читает `listFormat.json` и `REQUIRED_COLUMNS`, `OPTIONAL_COLUMNS`, `MAY_BE_EMPTY`, `FILE_SUFFIXES`, `MAX_UPLOAD_BYTES` |
| V16–V18, V20, V22: экран | `vitest run src/pages/__tests__/intake.test.tsx` | 22 passed; **до правки красные** V16 (`expected false to be true` — плашка не над полем ссылки), V18 (нет «каким должен быть файл»), V20 (`'C:\fakepath\список.csv'` вместо `''`); V17 — страж, зелёный и до правки |
| Бэкенд целиком, общая дев-база | `pytest -q` c `DATABASE_URL=…/cases` | 690 passed, 3 skipped — с первого раза, повтор не понадобился |
| Бэкенд целиком, своя чистая база | `pytest -q` c `DATABASE_URL=…/cases_ffe_tests` (схему поднимает сьют миграциями, как в CI) | 690 passed, 3 skipped |
| Фронт целиком | `vitest run` | 183 passed |
| Типы и стиль | `mypy src/ahrefs_cases`, `ruff check src tests`, `ruff format --check`, `tsc --noEmit`, `eslint --max-warnings 0 src`, `prettier --check src` | чисто |
| Гейты коммита | pre-commit, 29 хуков | passed на каждом коммите (на коммите спеки хуки кода пропущены — файлов кода нет) |
| Контур поставки | `python3 scripts/delivery_check.py --diff-base origin/main` | 0 ошибок; дифф 22 файла, net 777 при пределе 800 |
| CI на ветке поставки | GitHub Actions, PR #24 | delivery, gates, tests — pass на `ba50791` (код поставки целиком): https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36041318681 |

## Исполнение рисковых путей

`web/src/pages/intake/` — прогнал `node drive.mjs` (драйвер Chrome 154 по CDP,
headless) против боевой сборки ветки (`vite build` + `vite preview`) и API ветки
(`uvicorn check_app:app`) на копии дев-базы `cases_intake_check` (75
проектов); для сравнения — тот же сценарий на сборке и API `origin/main`.
Таблица по ссылке — через подменённый транспорт: `check_app.py` подменяет
только `gsheet_source._http_fetch` чтением локального CSV, разбор и проверка —
код ветки; настоящую чужую таблицу не трогали. at=2026-09-24

| Что | Ветка | `origin/main` |
|---|---|---|
| Тема (`prefers-color-scheme` + сброс `mantine-color-scheme-value`) | тёмная и светлая, `data-mantine-color-scheme` совпал | — |
| «?» у файла и у ссылки (наведение мышью) | обе карточки раскрылись, колонки 10 из 10 совпали; у файла — форматы, первый лист, разделитель, кодировка, 2 МБ, доступа по ссылке нет | у файла «?» нет |
| V1 книга без двух колонок | `400`, красная плашка под полем файла, «Принято из» нет | `200`, «Принято из «V1-…»», отклонено строк 1, «в файле нет колонки» |
| 18 настоящих файлов по очереди | 16 отказов под полем файла, 2 годных — «Принято из …» | — |
| V8 настоящий PDF под именем `.xlsx` | «не читается как книга Excel (BadZipFile)» | «сервер ответил 500» под полем ссылки |
| V13, V14, V15 — 6 ответов таблицы | 5 отказов под полем ссылки (закрытая — своим текстом), годная — «Принято из …» | — |
| V20 тот же файл второй раз | второй запрос ушёл, поле выбора пусто | запросов 0 — кнопка молчит |
| V22 файл 3,3 МБ | отказ у поля, запроса нет | — |
| Ошибки страницы (`Runtime.exceptionThrown`) | 0 | 0 |

Исполнение нашло два отказа, которых не видели тесты: файл больше 2 МБ
получал от сервера `413`, но прокси ловил `EPIPE` и отдавал «сервер ответил
500» (TestClient ходит мимо прокси и видит честный `413`); и `?usp=sharing` в
подсказке рвался переносом после «?». Оба исправлены и перепроверены тем же
прогоном. Снимки подсказок и отказов в обеих темах, а также «было» с
`origin/main` лежат рядом с драйвером (`ffe-shots/`, вне репозитория). После
проверки копия базы удалена, API, `vite preview` и Chrome остановлены.

## Ревью рисковых мест

**Транзакция БД: отказ случается до записи.** `check_fit` — первый шаг
`validate_table`, которую `accept` зовёт до `upsert_projects`; исключение
выходит из `_accept` раньше `session.commit()`, а `get_session` откатывает
сессию на ошибке. Держат это `_own_projects(writer) == 0` в V1 и V13 и
браузер: после отказа V1 те же домены в V12 пришли как «создано 10,
обновлено 0» — значит, отказ не записал ни одной строки.

**Широкий `except Exception` в `read_xlsx_stream`.** Внутри блока только
чтение книги openpyxl (`load_workbook`, `iter_rows`); приведение ячеек
`_cell_to_str` — наш код — вынесено наружу и так не прячется. Список типов не
годился: на четырёх видах брака нашлось три разных исключения, и каждое не
пойманное было пятисоткой.

**Безопасность: текст шапки возвращается человеку и пишется в лог.**
`_seen` показывает до шести ячеек первой строки (каждая — до 60 символов) тому
же пользователю, который их прислал; экран рисует их текстом React, не
разметкой. `intake_refused` пишет `reason` с этими ячейками в лог — так же,
как `intake_accepted` пишет имя файла; учётных данных в шапке списка нет, но
если отдел положит туда имя клиента, оно окажется в логе. Предел на экране
(`MAX_BYTES` в `SourceForm.tsx`) — удобство, а не защита: сервер держит
`MAX_UPLOAD_BYTES` как прежде, прямой вызов API получает `413`.

**Производительность.** Поиск нулевого байта смотрит 4096 символов
(`_BINARY_PROBE`); `data_rows()` теперь считается дважды — в `check_fit` и в
`validate_table` — на списке до сотни строк это микросекунды. Читатель книги
держит сырые значения (`cells`) до приведения — на книге до 2 МБ это
удвоение памяти на время разбора, не больше.

**Новый модуль вместо старого.** `ListHelp.tsx` заменил `SheetHelp.tsx`:
ссылок на старое имя в коде не осталось (tsc и сборка это держат), тест экрана
берёт `FILE_FORMAT`, `FILE_CSV`, `SHEET_ACCESS` из нового модуля.
`listFormat.json` читают две стороны — `ListHelp.tsx` и
`tests/test_intake_list_format.py`; переименование ключа в JSON краснит оба.

## Чего проверка НЕ доказывает

**Настоящий Google.** Путь ссылки исполнен с подменённой загрузкой байтов.
Что Google отдаёт на пустой лист и на несуществующий `gid` (пустой CSV или
ошибку — тогда это «таблица недоступна», а не «не подходит»), живьём не
проверено.

**Настоящий nginx.** На проде тело буферизует nginx (`client_max_body_size
3m`), и `413` сервера через него может прийти иначе, чем через прокси `vite`
(`502` или сам `413`). Браузер больше не отправляет файлы больше предела, так
что человек этого пути не увидит; прямой вызов API — увидит.

**Файлы из настоящего Excel.** Книги собраны openpyxl, PDF взят системный;
файлы, сохранённые Excel, LibreOffice или экспортом Google, не гонялись.
Цепочку кодировок поставка не меняла.

**Решения владельца.** Предел в сто строк на загрузку не вводится, русские
имена колонок не принимаются — оба вопроса открыты (спека, decisions).

## Verdict
- [x] READY FOR HANDOFF — подписал human:anthony at=2026-09-24 («Сливай и выкатывай» — импорт «как только будет зелёным и проверенным»)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **60**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
V6	assert "файл пуст" in response.json()["detail"]
V6	assert "тело запроса" not in response.json()["detail"]
V15	assert "не подходит" not in response.json()["detail"]
V15	assert sheet is not None
L68	assert response.status_code == 400, response.text  # type: ignore[attr-defined]
L68	assert isinstance(detail, str)
V1	assert detail.startswith("Файл «список.xlsx» не подходит: нет колонок period_start, geo.")
V1	assert ", ".join(HEADER) in detail
V1	assert _own_projects(writer) == 0
V2	assert "нет ни одной нужной колонки" in detail
V2	assert "В первой строке сейчас: «домен», «начало»" in detail
V2	assert ", ".join(HEADER) in detail
V3	assert "В первой строке сейчас: «domain|period_start|" in detail
V3	assert "Шапка не разделилась на колонки" in detail
V4	assert f"{name} — в шапке «{name.replace('_', ' ')}», переименуйте" in detail
V5	assert "только шапка — строк со списком нет" in detail
V7	assert f"Читается первый лист книги — «{first[0]}»" in detail
V7	assert "«Список»" in detail
V8	assert "не читается как книга Excel" in detail
V9	assert said in detail
V10	assert "нет колонки geo." in detail
V10	assert "В шапке дважды: domain" in detail
V13	assert detail.startswith("Таблица по ссылке не подходит: нет колонок client, owner.")
V13	assert ", ".join(HEADER) in detail
V13	assert _own_projects(writer) == 0
V14	assert said in detail
V14	assert ("gid=7" in detail) is names_the_sheet
V21	assert result.returncode == _EXIT_BAD_SOURCE
V21	assert "список не подходит: нет ни одной нужной колонки" in result.stderr
V21	assert "Traceback" not in result.stderr
V1	assert str(refused.value).startswith("нет колонки client.")
L123	assert isinstance(data, dict)
L123	assert isinstance(columns, list)
V19	assert [column["name"] for column in _columns()] == list(REQUIRED_COLUMNS)
V19	assert [column["name"] for column in _columns("optional")] == list(OPTIONAL_COLUMNS)
V19	assert may_be_empty == set(MAY_BE_EMPTY)
V19	assert column.get("what"), column
V19	assert column.get("example"), column
V19	assert column.get("what"), column
V19	assert help_data["fileSuffixes"] == list(FILE_SUFFIXES)
V19	assert help_data["maxMegabytes"] == MAX_UPLOAD_BYTES / _MEGABYTE
V6	assert "нет колонки" not in str(refused.value)
V16	expect(follows(screen.getByLabelText('Файл со списком'), refusal)).toBe(true);
V16	expect(follows(refusal, screen.getByLabelText('Ссылка на Google Sheet'))).toBe(true);
V16	expect(screen.queryByText(/Принято из/)).not.toBeInTheDocument();
V17	expect(follows(screen.getByLabelText('Ссылка на Google Sheet'), refusal)).toBe(true);
V17	expect(screen.queryByText(/Принято из/)).not.toBeInTheDocument();
V22	expect(follows(screen.getByLabelText('Файл со списком'), refusal)).toBe(true);
V22	expect(calls.filter((path) => path.startsWith('/api/intake'))).toEqual([]);
V20	expect(input.value).toBe('');
V20	expect(input.files).toHaveLength(0);
L76	expect(await screen.findByLabelText('каким должен быть файл')).toBeInTheDocument();
L76	expect(screen.getByLabelText('какой должна быть таблица')).toBeInTheDocument();
V18	expect(FILE_FORMAT).toMatch(/XLSX/);
V18	expect(FILE_FORMAT).toMatch(/CSV/);
V18	expect(FILE_FORMAT).toMatch(/2 МБ/);
V18	expect(FILE_FORMAT).toMatch(/первый лист/);
V18	expect(FILE_CSV).toMatch(/точка с запятой/);
V18	expect(FILE_CSV).toMatch(/Windows-1251/);
V18	expect(`${FILE_FORMAT} ${FILE_CSV}`).not.toMatch(/по ссылке|Авторизация/);
```

✅ **Каждое утверждение ведёт к примеру спеки** (L123 L68 L76 V1 V10 V13 V14 V15 V16 V17 V18 V19 V2 V20 V21 V22 V3 V4 V5 V6 V7 V8 V9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 22 code (+10 process docs) / +1070/-293 (net +777) |
| commits | 3 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_intake_list_format.py (новый оракул) |
| implement_retries | 3 — раскрытие карточки в jsdom шло 22 с и падало по таймауту (заменено проверкой значка и данных, L76); `max-lines-per-function` 81 > 80 у `SourceForm` (вынесен `FileField`); ruff SIM905 в помощнике теста |
| verify_fails_before_green | 2 по продуктовым оракулам — исполнение в Chrome нашло «сервер ответил 500» на файле больше 2 МБ (V22) и перенос внутри `?usp=sharing`; 1 по форме — breaker `net 812 > 800`, тесты ужаты до 777 без потери проверок |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
