# Verify report: screenshots-api

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M48–M53 | `tests/test_api_screenshots.py` (свои строки, свой каталог) | 6 passed |
| Приём списка на общем чтении тела | `tests/test_api_intake.py` (413 «МБ», 400 пустое) | зелёные |
| Удаление проекта | `tests/test_api_projects_delete.py` (след удаления с `screenshots: 0`) | 11 passed |
| Живой проход | стенд (API на коде ветки, миграция `d1e2f3a4b5c6` на копии), Chrome по CDP: `fetch` через прокси Vite | загрузка настоящего снимка 1440 × 1000 — 201, перекодирован 373 → 331 КБ; список — 1; картинка — 200 `image/png`, `nosniff`; текст вместо картинки — 415 «это не картинка PNG, JPEG или WebP»; удаление — 200, список пуст, каталог проекта пуст |

## Исполнение рисковых путей

- `src/ahrefs_cases/api/routers/screenshots.py` — прогнал `node step10.mjs` (Chrome по CDP, `fetch` из
  страницы через прокси Vite на uvicorn стенда), увидел: 201 на снимок 373 КБ, 200 и `nosniff` на
  картинку, 415 на текст, 200 на удаление и пустой каталог. Прокси nginx с пределом 3 МБ на стенде нет —
  загрузка большого скрина через сайт проверяется после выкатки (`observe_signal`). at=2026-10-07

## Ревью рисковых мест

**Безопасность.** Загрузка и удаление — под `require_right("edit_briefs")`, просмотр — под
`require_right("read")`. Картинка отдаётся с `X-Content-Type-Options: nosniff` и
`Content-Disposition: inline`: браузер не угадывает тип. Тело читает `read_body` с пределом по ходу
чтения — `Content-Length` не доверяем. Ключ файла берётся из базы и проходит `_inside` в
`storage.screenshots`.

**Транзакция БД.** `upload_screenshot` пишет файл, затем строку и `commit`; сбой коммита стирает файл
(`files.remove`) и пишет `screenshot_not_recorded` с исключением. `delete_screenshot` — строка и
`commit`, файл после. Дубль ловится до записи (`checksum`), гонка — уникальным ключом
`uq_screenshot_once_per_project`.

**Производительность.** `prepare`, `save`, `read` и удаление идут через `anyio.to_thread.run_sync`:
распаковка и перекодирование большой картинки не останавливают цикл событий.

**Новые модули.** `api/body.py` — одна функция; `api/routers/screenshots.py` — четыре эндпоинта.

## Чего проверка НЕ доказывает

- Что прокси сервера пропустит скрин 2,5 МБ — на стенде прокси нет; проверка после выкатки.
- Экрана загрузки ещё нет — последний PR этапа.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED
