# Plan: sheet-off-the-loop

## Шаги

1. `src/ahrefs_cases/api/routers/intake.py` — `read_gsheet` и `read_upload` через `asyncio.to_thread`: чтение Google
   и разбор книги не держат цикл событий единственного процесса API. Отказы приёма — прежние.
2. `src/ahrefs_cases/collect/ahrefs_transport.py` — `TransportResponse.units_per_row` из `x-api-units-cost-row`
   (`_header_optional_int`: нет заголовка или не число — `None`).
3. `src/ahrefs_cases/collect/provider.py`, `live.py`, `fixtures/provider.py` — `HistoryResult.units_per_row`: у live —
   заголовок, у fixture — `spec.row_units()` той же модели, что дала её units; пустой ответ — `None`.
4. `src/ahrefs_cases/collect/budget.py` — `record_spend` пишет `units_per_row`.
5. `README.md` (статус, PDF-бриф), шапка `collect/runner.py`; реестр Z52, концепт `ops/first-live-run.md`, журнал знаний.

## Уроки по затронутым путям (`archive/INDEX.md`)

- **L10** — закрытая таблица отвечает страницей входа со статусом 200: различитель `_ensure_csv` работает и в потоке —
  отказ тот же, проверен прежними тестами приёма.
- **L87** — колонка, которую никто не пишет, выглядит как данные и является пустотой: `units_per_row` заполняется
  с этой поставки, а у пустого ответа остаётся пустой, а не нулём.
- **L251** — цену строки хранит журнал фактов: у живого ответа без заголовка — `None`, модель туда не подставляется.

## Rejected alternatives

- Асинхронный клиент Google в `gsheet_source` — отвергнуто, потому что `read_gsheet` синхронен и им пользуется консоль (`intake/accept.load_source`); поток даёт ту же свободу циклу событий без второй реализации чтения.
- Удалить колонку `units_per_row` — отвергнуто, потому что цена строки — то, чем проверяют модель цены на живых запросах (`docs/UNITS_OPTIMIZATION.md`), а заголовок Ahrefs присылает её бесплатно.
