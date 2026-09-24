# Tasks: journal-small-fixes

Уроки по затронутым путям — в `plan.md`.

- [x] T1: оракулы W1–W6 (pytest в `tests/test_api_runs.py`, vitest в
      `ops.test.tsx`) — красные до правки.
- [x] T2: судьба прогона — домен через `to_unicode` в `api/routers/runs.py`.
- [x] T3: `budget.live_runs` — какие прогоны живые, тем же `_live_run`; `RunRow`
      несёт `live` и `mode`; авторы и режим — одним запросом на страницу.
- [x] T4: экран журнала — пометка условных units и незаписанного режима.
- [x] T5: браузер на копии базы и боевой сборке; pytest на своей копии; vitest,
      tsc, eslint; `delivery_check`; реестр (Z47), концепт; архив и уроки
      (L221–L222); PR и зелёный CI.
