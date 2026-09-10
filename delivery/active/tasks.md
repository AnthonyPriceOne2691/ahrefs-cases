# Tasks: Ф2а — приём списка и сбор на фикстурах

Порядок снизу вверх: каждый следующий шаг опирается на проверенный предыдущий
(plan.md → Approach).

## Приём: форма входа
- [x] `config/projects.example.csv` → десять обязательных полей §4 + служебные
- [x] `intake/rows.py`: `RawRow`, `RawTable`, номера строк как в Excel
- [x] `intake/normalize.py`: домен → канонический хост (punycode, www, путь, порт, креды)
- [x] тест: golden-таблица нормализации, 25 случаев + канарейка (B4)

## Приём: источники
- [x] `intake/csv_source.py`: кодировка цепочкой, разделитель по заголовку (B3)
- [x] `intake/xlsx_source.py`: `openpyxl`, `data_only=True`, даты и числа к строкам
- [x] `intake/gsheet_source.py`: ссылка → экспорт, HTML вместо CSV = отказ в доступе
- [x] тест: три источника дают идентичную таблицу (B2)

## Приём: правила и отчёт
- [x] `intake/validate.py`: десять колонок таблицей, приведение типов — функциями
- [x] `intake/report.py`: `IntakeReport` + сводка по причинам
- [x] `intake/upsert.py`: ключ `(domain, target_mode, period_start)`, `status` не перезаписывается (B5)
- [x] тест: 100 строк, 7 негодных → 93 проекта, причина по каждой строке (B1)
- [x] тест: повторная загрузка обновляет; один домен с разными периодами — два проекта (B5)

## Провайдер
- [x] `collect/endpoints.py`: `EndpointSpec` данными — шесть history-endpoint'ов
- [x] `collect/provider.py`: `AhrefsProvider(Protocol)`, `HistoryRequest/Point/Result`
- [x] модель стоимости в `EndpointSpec` — одна функция на оба провайдера
- [x] `collect/ahrefs_transport.py` + `collect/live.py`: ретраи только осмысленные, разбор заголовков цены
- [x] тест: 401 не повторяется, 429 повторяется, `select` минимальный; live без ключа — A5/B12

## Фикстуры и генератор
- [x] `collect/fixtures/`: семь сценариев + `empty`, формы таблицей, детерминизм на sha256
- [x] `data/fixtures/scenarios.yml`: 104 домена явно, опечатка в сценарии — ошибка, не дефолт
- [x] `collect/fixtures/provider.py` + `collect/factory.py`: выбор провайдера по конфигу
- [x] тест: детерминизм по seed и обратная сторона — seed влияет (B7)
- [x] тест: `data_hole` — месяцы отсутствуют, а не равны нулю (B8); `empty` бесплатен (B11)

## Прогон
- [x] `collect/plan.py`: задачи шага 1, границы истории (`history_lead_months`)
- [x] `collect/series.py`: запись `MetricPoint` через `ON CONFLICT DO UPDATE`
- [x] `collect/run_journal.py`: `Run`/`RunItem`, системный пользователь для CLI, три исхода прогона
- [x] `collect/budget.py`: строка `UnitsLedger` на запрос, сумма считается запросом к журналу
- [x] `scripts/run_collect.py`: `intake` / `collect` / `all` (HTTP — Ф5)
- [x] тест: 100 доменов, httpx запрещён → `done`, точки в базе, ноль запросов наружу (B6)
- [x] тест: пустая история → `skipped_no_data`, прогон продолжается; падение одного → `partial` (B11)
- [x] тест: короткая история принимается с пометкой `short_history` (B9)
- [x] тест: `UnitsLedger` — 100 строк, сумма 5000 по модели стоимости (B10)

## Закрытие
- [x] `eval-smoke.md`: сквозной прогон файл → база → отчёт
- [x] покрытие ядра 94 % при пороге 80 % (§10 документа реализации)
- [x] `decisions.md` заполняется по ходу: 25 решений на три блока работ
