# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** ждёт подписи владельца — 9 утверждений из 66 не ведут к
примеру спеки (дайджест ниже; заявленное «n/a» оказалось преждевременным)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34601595197
**Commit:** 0f54885

## Shape oracles
- [x] PASS — pre-commit, 29 хуков, упавших 0
- [x] PASS — предохранители: net_loc 776 при пороге 800, файлов 15 из 25
- [x] PASS — import-linter: оба контракта держатся (`api` → `classify` → `collect`)
- [x] PASS — DRY-гейт: снимок 1 clone-пара, было 2 после правки — дубль вынесен

## Behavior oracles
- [x] PASS — pytest 401 passed, 1 skipped; покрытие ядра 94 %
- [x] PASS — примеры E1–E12 закрыты тестами, ручных среди них нет

## Product oracles
- [x] PASS — XLSX на десять строк принят по HTTP, повторная загрузка обновляет
- [x] PASS — битая строка отклонена с номером строки и причиной, годные приняты
- [x] PASS — смета показывает цену и остаток, не открывая прогона и не тратя units
- [x] PASS — прогон из очереди и смета берут окна точек из одной версии порогов

## Ревью рисковых мест

**Смета обязана быть ценой того прогона, который начнётся.** Это главное
свойство поставки, и оно не держалось: окна точек читал только CLI, а задача
звала сбор без них. Проверяется не «похожестью чисел», а сравнением **входов
двух путей** — по отдельности оба пути выглядели исправными, и в этом всё дело.

**L57 ударил второй раз, ровно по своему описанию.** `HTTP_413_REQUEST_ENTITY_
TOO_LARGE` объявлена устаревшей, `filterwarnings = error` превращает это в
исключение — отказ по размеру приходил пятисоткой. Путь ошибки тестируется реже
успешного, поэтому без теста на предел это уехало бы в прод незамеченным.
Взято нынешнее имя `HTTP_413_CONTENT_TOO_LARGE`; в грабли карты репозитория
дописано, что дело не в одной константе.

**Пятисотка вместо отказа нашлась и у Google Sheet.** `httpx` бросал сетевую
ошибку сырой, и «сеть недоступна» читалось человеком как «сервис сломан».
Превращение живёт в загрузчике (`_http_fetch`), а не в роутере: причина одна и
та же для всех вызывающих, а действие человека одно — открыть доступ или
прислать файлом.

**Деньги.** Смета ничего не покупает: план строится по базе, остаток квоты стоит
0 units и в разработке берётся из фикстуры. Прогон при этом не открывается —
иначе посмотревший цену и передумавший держал бы резерв units и строку в журнале.

**Предел размера считается по ходу чтения, а не по заголовку.** `Content-Length`
присылает клиент; верить ему — значит принять тело любого размера от того, кто
соврал.

**Безопасность.** Приём закрыт правом `run` (это запись в базу сервиса), смета —
правом `read`: посмотреть цену полезно и тому, кто сам не запускает. Имя файла
используется только для формата и происхождения, путь из него не строится.

**Транзакция БД.** Приём проверяет всю таблицу до первой записи — сто строк не
оставят базу наполовину заполненной из-за сороковой. Свойство было у `accept` и
сохранено: роутер его не обходит.

## Что осталось за границей

Экран загрузки — следующая поставка (`web-intake`). Смета ступеней 2 и 3 не
считается: до классификации неизвестно, за кого платить.
## Assertion digest (ревью ожиданий, не кода)

База: `0f54885~1` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **66**, из них без ссылки на пример спеки:
**9**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
L51	assert sheet is not None
E1	assert response.status_code == 200
E1	assert body["accepted"] == GOOD_ROWS
E1	assert body["created"] == GOOD_ROWS
E1	assert body["rejected_rows"] == 0
E1	assert body["origin"] == "список.xlsx"
E2	assert body["accepted"] == GOOD_ROWS
E2	assert body["rejected_rows"] == 1
E2	assert rejection["row_no"] == GOOD_ROWS + 2
E2	assert rejection["field"] == "domain"
E2	assert rejection["reason"] == "missing_field"
E2	assert body["by_reason"]["missing_field"] == 1
E3	assert again["created"] == 0
E3	assert again["updated"] == GOOD_ROWS
E4	assert response.status_code == 400
E4	assert "не понимаю формат" in response.json()["detail"]
E5	assert response.status_code == 413
E5	assert "МБ" in response.json()["detail"]
-	assert response.status_code == 400
-	assert "файла нет" in response.json()["detail"]
E6	assert response.status_code == 400
E6	assert "недоступна по ссылке" in response.json()["detail"]
-	assert response.status_code == 400
-	assert response.status_code == 400
-	assert "не похоже на ссылку Google Sheet" in response.json()["detail"]
E7	assert response.status_code == 403
E7	assert "run" in response.json()["detail"]
-	assert (
-	assert response.status_code == 200
E8	assert body["projects"] == GOOD_ROWS
E8	assert body["units_estimated"] == asyncio.run(_plan_units())
E8	assert body["requests_planned"] > 0
E8	assert body["scheme_lines"]
-	assert client.get("/api/runs", headers=_headers(client)).json() == []
E9	assert body["may_start"] is False
E9	assert body["verdict"] == "not_enough"
E9	assert "не хватает units" in str(body["reason"])
E9	assert body["quota_left"] == 1
E10	assert body["verdict"] == "unknown"
E10	assert body["may_start"] is False
E10	assert body["quota_left"] is None
-	assert response.status_code == 200
E12	assert seen, "задача не позвала сбор — проверять нечего"
E12	assert seen[0] is not None
E12	assert seen[0] == asyncio.run(_expected())
E1	expect(labels(['read', 'run'])[0]).toBe('Загрузка');
E1	expect(labels(['read'])).not.toContain('Загрузка');
E3	expect(await screen.findByText('принято 10')).toBeInTheDocument();
E3	expect(screen.getByText('создано 10')).toBeInTheDocument();
E3	expect(screen.getByText('обновлено 0')).toBeInTheDocument();
E4	expect(await screen.findByText('12')).toBeInTheDocument();
E4	expect(screen.getByText('дата не разобрана')).toBeInTheDocument();
E5	expect(await screen.findByText(/не понимаю формат файла/)).toBeInTheDocument();
E6	expect(await screen.findByText(/таблица недоступна по ссылке/)).toBeInTheDocument();
E8	expect(await screen.findByText('units по смете 1980')).toBeInTheDocument();
E8	expect(screen.getByText(/Остаток квоты: 9\s?500/)).toBeInTheDocument();
E8	expect(screen.getByText(/organic-traffic-history/)).toBeInTheDocument();
E9	expect(await screen.findByText(/не хватает units: остаток 300/)).toBeInTheDocument();
E9	expect(screen.getByTestId('start-run')).toBeDisabled();
E10	expect(await screen.findByText(/остаток квоты Ahrefs неизвестен/)).toBeInTheDocument();
E10	expect(screen.getByText('Остаток квоты: неизвестен')).toBeInTheDocument();
E10	expect(screen.getByTestId('start-run')).toBeDisabled();
E11	expect(await screen.findByText(/Прогон №7/)).toBeInTheDocument();
E12	expect(await screen.findByText(/прогон 4 уже идёт/)).toBeInTheDocument();
E13	expect(await screen.findByText('units по смете 0')).toBeInTheDocument();
E13	await waitFor(() => expect(screen.getByText('units по смете 1980')).toBeInTheDocument());
```

Привязаны к примерам: **E1 E10 E11 E12 E13 E2 E3 E4 E5 E6 E7 E8 E9 L51**. Остальные 9 — нет.

Читать нужно **только строки с `-` в первой колонке**: их ожидание
ничем не подписано. Подпись: `asserts_reviewed_by: human:… at=…`.

asserts_without_example: 9

**Откуда взяты ожидания девяти непривязанных утверждений.** Все девять — из
того же требования, что и примеры спеки, но своими именами их спека не назвала:

- пустое тело → `400` и «файла нет»: обратная сторона E5 (предел сверху) —
  «файла нет» и «файл велик» оба обязаны быть отказом, а не «принято 0»;
- недоступная таблица и ссылка не на таблицу → `400`: то же требование, что E6,
  для двух других причин недоступности (сеть и форма ссылки);
- приём без токена → `401`: это запись в базу сервиса, и она закрыта наравне с
  остальными записывающими роутерами (Ф5);
- смета не открывает прогона и видна тому, кому запуск запрещён: оба
  утверждения — из строки спеки «смета не стоит units» и из приёма Ф5
  «смотреть и применять — разные действия».

Подпись остаётся за владельцем: гейт прав в том, что «n/a» надо заслужить.

## Verdict
- [x] READY FOR HANDOFF

## Harness metrics (this shipment)

<!-- заполнено вручную на ретрофите: `delivery_metrics.py` меряет от базы до
     HEAD, а HEAD ушёл вперёд на следующую поставку. Числа — те, что снял
     `delivery_check --diff-base HEAD~1` в момент handoff. -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 15 code (+9 process docs) / +825/-49 (net +776) |
| commits | 1 (+1 на перенос в архив) |
| time_to_accepted_spec | 0.0h (спеку подписал владелец выбором поставки) |
| rework_after_done | 0 |
| harness_hardened | yes — tests/test_api_intake.py (новый оракул: приём по HTTP, смета, сравнение входов двух путей запуска) |
| implement_retries | 3 — устаревшая константа `413`, сетевая ошибка Google, разъехавшийся код отказа в тесте |
| verify_fails_before_green | 0 (CI зелёный с первого прогона) |
| est_token_or_cost | n/a |
