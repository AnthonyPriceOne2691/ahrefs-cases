---
type: Reference
title: Карта репозитория
description: Где входные точки, где что лежит, где грабли.
status: stable
tags: [repo, onboarding]
generated:
  by: claude/agent
  at: 2026-09-11T21:00:00Z
stale_after: 2026-12-10
implementation:
  - src/ahrefs_cases/api/main.py
  - src/ahrefs_cases/workers/main.py
  - src/ahrefs_cases/config/__init__.py
  - pyproject.toml
---

# Входные точки

| Что | Как запускается |
|---|---|
| Основная работа | `python scripts/run_collect.py <команда>`: `intake`, `collect`, `stage2`, `classify`, `recalc`, `preview`, `diagnose`, `explain`, `all` |
| Тесты | `.venv/bin/python -m pytest -q` — нужна дев-база Postgres |
| Гейты формы | `.venv/bin/python -m pre_commit run --all-files` (27 хуков) |
| Контур поставки | `python scripts/delivery_check.py [--diff-base REF]` |
| Канон знаний | `python scripts/okf_validate.py`, `python scripts/okf_sync_gate.py --staged` |
| API | `src/ahrefs_cases/api/main.py` — пока только health, наполнится в Ф5 |

# Где что лежит

Слои идут сверху вниз, и направление зависимостей проверяется import-linter:
`api`/`workers` → `cases`/`export` → `classify` → `collect`/`intake` → `storage`
→ `config`.

| Каталог | Что в нём | Граница |
|---|---|---|
| `src/ahrefs_cases/intake/` | приём списка: источники, нормализация, отказы | не знает про Ahrefs |
| `src/ahrefs_cases/collect/` | план, провайдеры, кэш, журнал, смета units | **не знает про `classify`** — классификация обязана быть переигрываемой |
| `src/ahrefs_cases/classify/` | точки, дельты, правила, вердикты, пересчёт, предпросмотр, диагностика | не ходит в сеть |
| `src/ahrefs_cases/storage/` | модели и сессия | ничего не решает |
| `src/ahrefs_cases/config/` | типизированные настройки | **единственное место `os.getenv`** |
| `delivery/` | контур поставки: активная, архив, уроки | вне предохранителей размера |
| `knowledge/` | этот канон | вне предохранителей размера |
| `docs/` | часть в git (находки, экономия, чеклисты), часть вне (ТЗ, планы фаз) | клиентское — вне git по варианту D |

Новый модуль кладётся в слой, которому он принадлежит по зависимостям, а не по
теме: если он нужен и сбору, и классификации, его место ниже обоих.

# Грабли

Единственный раздел, который нельзя вывести из кода.

- **`.git/info/exclude` действует только на неотслеживаемые пути.** После
  `git rm --cached` любой `git add -A` вернёт файл в индекс. Различитель —
  `git ls-files`, а не отсутствие файла в `git status`.
- **Коммит может не состояться, а вывод выглядеть успешным.** Хуки правят файлы
  (ruff format) и отклоняют коммит. Проверять `git log`, а не отсутствие ошибки.
  Тем же способом однажды промолчал `git mv` при переносе поставки в архив.
- **Локально зелено ≠ зелено.** Venv гейтов ставит проект, дев-база уже
  прогнана миграциями, а CI чист. Три отказа подряд пришли отсюда.
- **`hash()` строки рандомизируется между процессами.** Генератор фикстур
  обязан сеяться `sha256`, иначе golden-таблицы краснеют через раз.
- **`sa.Enum(StrEnum)` хранит в Postgres имена, а не значения.**
  `ALTER TYPE ... ADD VALUE` со значением проходит зелёным и падает на первой
  вставке. Проверять `enum_range`.
- **Закрытая Google Sheet отвечает страницей входа со статусом 200.** Разбор
  такого ответа как CSV даёт «принято 0, отклонено 0» — ложь успехом.
- **`detect-secrets` считает секретом hex-идентификаторы ревизий alembic.**
  Лечится `pragma: allowlist secret` на строке, не расширением baseline.
- **Дев-база живёт между прогонами** и копит следы ручных запусков CLI. Тест,
  читающий «все проекты», обязан чистить внутри своей транзакции.
- **Пороги заказчика вне репозитория.** Тест, стоящий на `config/thresholds.yml`,
  зелёный только на машине автора; в git — нейтральные умолчания.

# Related

- [../engineering/index.md](../engineering/index.md)
- Уроки о том, как мы работаем: `delivery/archive/INDEX.md` (L1–L34).
