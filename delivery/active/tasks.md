# Tasks: Ф2а — приём списка и сбор на фикстурах

Порядок снизу вверх: каждый следующий шаг опирается на проверенный предыдущий
(plan.md → Approach).

## Приём: форма входа
- [ ] `config/projects.example.csv` → десять обязательных полей §4 + служебные
- [ ] `intake/rows.py`: `RawRow` (значения + номер строки в источнике)
- [ ] `intake/normalize.py`: домен → канонический хост (punycode, www, путь, точка в конце)
- [ ] тест: golden-таблица нормализации, включая мусор (B4)

## Приём: источники
- [ ] `intake/csv_source.py`: определение кодировки, цепочка fallback (B3)
- [ ] `intake/xlsx_source.py`: `openpyxl`, `data_only=True`, явное приведение дат
- [ ] `intake/gsheet_source.py`: ссылка `/edit` → `/export?format=csv&gid=`, чистая функция + таблица примеров
- [ ] тест: три источника с одинаковым содержимым дают идентичный отчёт (B2)

## Приём: правила и отчёт
- [ ] `intake/validate.py`: десять обязательных полей таблицей правил, не лестницей `if`
- [ ] `intake/report.py`: `IntakeReport` (`accepted`, `created`, `updated`, `rejected[]`)
- [ ] `intake/upsert.py`: проект по домену — создать или обновить (B5)
- [ ] тест: 100 строк, 7 негодных → 93 проекта, отчёт с причинами построчно (B1)
- [ ] тест: повторная загрузка не удваивает проекты (B5)

## Провайдер
- [ ] `collect/endpoints.py`: `EndpointSpec` данными — шесть history-endpoint'ов
- [ ] `collect/provider.py`: `AhrefsProvider(Protocol)`, `HistoryResult(rows, units)`
- [ ] модель стоимости в `EndpointSpec` — одна функция на оба провайдера
- [ ] `collect/ahrefs_transport.py` + `AhrefsLive`: httpx, `x-api-units-cost-*`, ретраи 1/5/30 с
- [ ] тест: `AHREFS_PROVIDER=live` без ключа падает на старте (B12, регрессия A5)

## Фикстуры и генератор
- [ ] `collect/fixtures/generator.py`: семь сценариев §1a, детерминизм по `(scenario, seed, domain)`
- [ ] `data/fixtures/scenarios.yml`: явное сопоставление домен → сценарий
- [ ] `collect/fixtures/provider.py`: `AhrefsFixture` поверх генератора
- [ ] тест: два вызова с одним seed дают идентичные серии (B7)
- [ ] тест: `data_hole` — месяцы отсутствуют, а не равны нулю (B8)

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
