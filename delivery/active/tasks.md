# Tasks: sqlalchemy-2-1

Спека — `spec.md` (примеры M115–M116).

- [x] `pyproject.toml`: `sqlalchemy[asyncio]>=2.1,<2.2`; `uv.lock` — `scripts/lock_deps.sh --upgrade-package sqlalchemy`:
  2.0.54 → 2.1.4, остальные пакеты прежние — M116.
- [x] `collect/cache.share_twin_points`: `.ext(distinct_on(…))` вместо `.distinct(expr)` — M115.
- [x] Repro: на 2.1.4 с прежним вызовом тесты кэша падают `SADeprecationWarning` (как 24.09 у 47 тестов CI).
- [x] Полный сьют на 2.1.4 нашёл второе устаревание: `Result.tuples()` (`api/run_rows.py`, журнал прогонов) — под
  `filterwarnings = error` 30 тестов API отвечали 500. Строки 2.1 сами ведут себя как кортежи: `.all()`. Оракул
  lock-файла (`test_dependency_lock.py`, K1) прибит к 2.1.4. После — 897 passed, 12 skipped.
- [ ] CI.

## Уроки по затронутым путям (`archive/INDEX.md`)

- **L223** — зависимость без верхней границы и без lock-файла — решение о версии, отданное чужому релизу: граница
  снова есть (`<2.2`), версия прибита lock-файлом, подъём — своей поставкой.
- **L152** — перенос месяцев между кампаниями с границей: DISTINCT ON берёт свежую копию месяца той же страны; запрос
  меняет только способ сказать DISTINCT ON, не его смысл.
