# Tasks: Ф1 — скелет и контракты

Порядок снизу вверх: каждый шаг проверяется предыдущим (plan.md → Approach).

## Конфиг и зависимости
- [ ] `pyproject.toml`: зависимости под Ф1, ruff, mypy strict, pytest
- [ ] `src/ahrefs_cases/config/`: `_base.py`, `ahrefs.py`, `storage.py`, `auth.py`, `classify.py`, `export.py`
- [ ] fail-fast на старте: `AHREFS_PROVIDER=live` без ключа → внятная ошибка (A5)
- [ ] тест: дефолты без `.env`, провайдер `fixture` (A4)

## Хранилище
- [ ] `storage/models/`: User, Project, MetricPoint, Run, RunItem, Verdict, Ruleset, Case, CaseArtifact, UnitsLedger
- [ ] `storage/session.py`: async engine, sessionmaker
- [ ] Alembic: `alembic.ini`, `migrations/env.py`, первая ревизия
- [ ] тест: upgrade → downgrade на пустой базе (A1)

## Дев-окружение
- [ ] `docker-compose.dev.yml`: postgres, redis, api (reload), web (vite)
- [ ] `Dockerfile` бэкенда — с системными библиотеками WeasyPrint (нужны в Ф4)
- [ ] `Dockerfile` фронта для дева

## Каркасы
- [ ] `api/main.py`: FastAPI, `GET /api/health` в трёх состояниях (A2, A3)
- [ ] `api/routers/`: заготовки по `docs/IMPLEMENTATION_V3.md` §9
- [ ] `workers/`: точка входа RQ, без задач
- [ ] `web/`: Vite + React + Mantine, токены liquid glass, светлая и тёмная темы
- [ ] раскладка приведена к документу реализации (`api/`, `workers/`, `web/`)

## Инварианты как проверки
- [ ] тест на импорты: ядро не тянет FastAPI и RQ
- [ ] CI: линтеры, типы, тесты на push

## Волна В1 — в конце фазы
- [ ] развернуть ② CQG (11 шагов) + ④ гейт мержа
- [ ] первый прогон гейтов **красный** либо с непустым числом просмотренных файлов
- [ ] `ci-oracles` и `shape-oracles` в STATUS обновить по факту
