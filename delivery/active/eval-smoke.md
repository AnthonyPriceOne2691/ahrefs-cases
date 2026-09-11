# Eval smoke — this shipment

Derived from spec acceptance. Run during verify.

- [x] E1 — upstream SPEC прочитан, версия 0.2 совпала с pinned; записано в `knowledge/log.md`
- [x] E2 — `okf_validate.py`: 0 error, 0 warning, 16 файлов
- [x] E3 — правка `classify/rules.py` без правки концепта: гейт **красный**, назван `groups-and-thresholds.md`
- [x] E4 — без правки кода гейт зелёный: 8 mapped concepts
- [x] E5 — `stale_after` на карте стоит (2026-12-10), `--check-stale` в норме молчит
- [x] E6 — `AGENTS.md` отправляет в `knowledge/index.md` до догадок
- [x] E7 — 267 тестов и 29 хуков зелёные; `gate-coverage` видит оба новых гейта
