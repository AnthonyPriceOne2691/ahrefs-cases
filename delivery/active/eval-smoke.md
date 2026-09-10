# Eval smoke — this shipment

Derived from spec acceptance. Run during verify.

- [ ] `python3 scripts/run_collect.py --file config/projects.example.csv` — приём проходит, отчёт печатает `accepted/rejected`
- [ ] тот же файл повторно — проекты не удваиваются (`created=0, updated=N`)
- [ ] прогон на 100 синтетических доменов завершается `completed` без сети
- [ ] `MetricPoint` непуст по каждому принятому проекту; `UnitsLedger` показывает условный расход
