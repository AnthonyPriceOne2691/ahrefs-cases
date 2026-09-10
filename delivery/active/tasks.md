# Tasks: Ф1 — скелет и контракты

Порядок снизу вверх: каждый шаг проверяется предыдущим (plan.md → Approach).

## Конфиг и зависимости
- [x] `pyproject.toml`: зависимости под Ф1, ruff, mypy strict, pytest
- [x] `src/ahrefs_cases/config/`: `_base.py`, `ahrefs.py`, `storage.py`, `auth.py`, `classify.py`, `export.py`
- [x] fail-fast на старте: `AHREFS_PROVIDER=live` без ключа → внятная ошибка (A5)
- [x] тест: дефолты без `.env`, провайдер `fixture` (A4)

## Хранилище
- [x] `storage/models/`: User, Project, MetricPoint, Run, RunItem, Verdict, Ruleset, Case, CaseArtifact, UnitsLedger
- [x] `storage/session.py`: async engine, sessionmaker
- [x] Alembic: `alembic.ini`, `migrations/env.py`, первая ревизия
- [x] тест: upgrade → downgrade на пустой базе (A1)

## Дев-окружение
- [x] `docker-compose.dev.yml`: postgres, redis, api (reload), web (vite)
- [x] `Dockerfile` бэкенда — с системными библиотеками WeasyPrint (нужны в Ф4)
- [~] `Dockerfile` фронта для дева — vite поднимается из образа `dev`, отдельный образ нужен только для прода (Ф9)

## Каркасы
- [x] `api/main.py`: FastAPI, `GET /api/health` в трёх состояниях (A2, A3)
- [~] `api/routers/`: только health. Пустые роутеры не заводим — роутер без реализации это ложное обещание в схеме OpenAPI; приходят вместе с логикой
- [x] `workers/`: точка входа RQ, без задач
- [x] `web/`: Vite + React + Mantine, токены liquid glass, светлая и тёмная темы
- [x] раскладка приведена к документу реализации (`api/`, `workers/`, `web/`)

## Инварианты как проверки
- [x] тест на импорты: ядро не тянет FastAPI и RQ
- [x] CI: линтеры, типы, тесты на push

## Волна В1 — в конце фазы
- [ ] развернуть ② CQG (11 шагов) + ④ гейт мержа
- [ ] первый прогон гейтов **красный** либо с непустым числом просмотренных файлов
- [ ] `ci-oracles` и `shape-oracles` в STATUS обновить по факту

## Найдено и исправлено по ходу

- **`populate_by_name` в конфиге.** Без него конструктор `Settings` принимает
  только алиас переменной окружения, а `AhrefsSettings(provider="live")` молча
  игнорируется вместе с `extra="ignore"` — то есть тест A5 был бы зелёным, ничего
  не проверив. Поймано первым же прогоном.
- **ENUM-типы не удалялись в downgrade.** Autogenerate создаёт их неявно, а в
  downgrade не пишет `DROP TYPE`: цикл upgrade → downgrade → upgrade падал на
  `DuplicateObject`. Миграция «работала» ровно один раз. Проверка типов после
  downgrade оставлена в тесте A1.
- **Health зависел от сессии из зависимости** и отвечал 500 при мёртвой базе:
  ошибка возникала вне `try` обработчика. Переписан на собственную короткую
  пробу с таймаутом — теперь 503 с причиной (A3).
- **`pydantic.mypy`** — без плагина strict-режим давал 24 ошибки на пустом
  каркасе, считая поля с дефолтом обязательными аргументами.
