# Eval smoke — this shipment

- [x] M113 — шаг vitest в CI, без `continue-on-error`
- [x] M114 — конфиг не глушит необработанные ошибки; замер — код 1
- [x] Исполнение: команда шага `npm test --prefix web` из корня — 25 файлов, 243 теста, код 0; CI ветки повторяет её
