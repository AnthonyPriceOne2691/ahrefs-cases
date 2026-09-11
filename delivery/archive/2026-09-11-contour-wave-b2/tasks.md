# Tasks: волна В2 — ③ OKF

Уроки архива, применимые к диффу: L7/L16 (объявление, живущее прозой, теряется),
L14 (различитель — `git log`, а не отсутствие ошибки) — см. plan.md.

## Preflight
- [x] upstream SPEC прочитан, версия сверена с pinned (0.2 = 0.2)
- [x] расхождений нет — правка канона не потребовалась, запись в `log.md` bundle'а

## Bundle
- [x] корень: `index.md` с разделами и «чего здесь нет намеренно», `log.md`
- [x] `product/overview.md` — воронка и её порядок
- [x] `classification/groups-and-thresholds.md` — группы, версии, границы метода
- [x] `classification/points-a-b.md` — точки А/Б и чем они ограничены
- [x] `collection/units-cost-model.md` — замеренная формула и следствия
- [x] `collection/collection-scheme.md` — история против точек, принятый маршрут
- [x] `collection/data-coverage.md` — три состояния отсутствия данных
- [x] `ops/first-live-run.md` — порядок первого живого захода
- [x] `references/repo-map.md` — вход, слои, грабли; со `stale_after`

## Гейты
- [x] `okf_validate.py` и `okf_sync_gate.py` из приложений канона дословно
- [x] оба подключены к pre-commit; в CI шаги уже ждали скриптов
- [x] проверено, что гейт синхронности **краснеет** на правке кода без канона
- [x] адаптация вызова записана в `scripts/lint/adapted.json`

## Объявления
- [x] крючок в `AGENTS.md`: читать `knowledge/index.md` до догадок
- [x] `delivery/STACK-ACCEPTANCE.md`: ③ deployed, stack `okf@0.2`
- [x] `stack:` в STATUS активной поставки
