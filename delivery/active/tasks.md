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
- [ ] `collect/plan.py`: список задач шага 1 по проектам прогона
- [ ] `collect/series.py`: запись `MetricPoint` (уникальность `project, metric, date, source`)
- [ ] `collect/run_journal.py`: `Run` и `RunItem` со статусом и причиной
- [ ] `collect/budget.py`: строка `UnitsLedger` на каждый запрос, units условные
- [ ] `scripts/run_collect.py`: запуск прогона из командной строки (HTTP — Ф5)
- [ ] тест: 100 доменов, сокет заглушен → `completed`, точки в базе, ноль сетевых вызовов (B6)
- [ ] тест: пустая история → `skipped/no_data`, прогон продолжается (B11)
- [ ] тест: короткая история принимается с пометкой (B9)
- [ ] тест: `UnitsLedger` — 100 строк, сумма по модели стоимости (B10)

## Закрытие
- [ ] `eval-smoke.md`: сквозной прогон файл → база → отчёт
- [ ] покрытие ядра ≥ 80 % (§10 документа реализации)
- [ ] `decisions.md` заполняется **по ходу**, не перед handoff
