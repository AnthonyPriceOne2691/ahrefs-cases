# Eval smoke — this shipment

Сквозной путь: собранные серии → вердикт с объяснением. Ahrefs не трогается.

```
$ python3 scripts/run_collect.py classify
$ python3 scripts/run_collect.py explain example.com
```

- [x] `classify` печатает версию порогов и распределение по четырём группам
- [x] сумма по группам равна числу классифицированных проектов
- [x] `explain` показывает каждое условие: факт, порог, сработало ли, решает оно или справочно
- [x] у «хороших» видно, что сработали и главная метрика, и подтверждающая
- [x] повторный `classify` не плодит вердикты: один проект на одну версию порогов

Прогнано 2026-09-10:

```
$ python3 scripts/run_collect.py classify
  пороги версии 0.1.0-draft · проектов классифицировано: 3
  good: 3, medium: 0, poor: 0, insufficient_data: 0

$ python3 scripts/run_collect.py explain example.com
  example.com: good (пороги 0.1.0-draft, score 19913)
  ✓ good.org_traffic_pct      факт 139.4   порог 50.0   [решает]
  ✓ good.org_traffic_abs      факт 65985.0 порог 1000.0 [решает]
  ✓ good.refdomains_pct       факт 84.8    порог 30.0   [справочно]
  ✓ good.kw_top10_pct         факт 139.4   порог 40.0   [справочно]
  ✓ good.supporting_required  факт 2.0     порог 1.0    [решает]
  ✓ good.months_after_start   факт 18.0    порог 6.0    [решает]
```
