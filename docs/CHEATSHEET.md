# Шпаргалка по проекту

## Коротко

Раньше кейс для клиента собирали руками: открыть Ahrefs, выписать цифры «было →
стало», нарисовать графики, свести всё на лист. Час-два на один кейс — а на
полсотни проектов такого времени не находит никто.

Сервис делает это сам. На вход — список проектов с периодами работ, на выход —
готовые PDF-кейсы по тем проектам, где результат действительно есть. Внутри он
берёт историю из Ahrefs, сравнивает начало работ с концом, раскладывает проекты
на четыре группы и собирает лист только для достойных: числа, графики роста и
короткий текст — всё в одном файле на страницу.

Что это даёт агентству: кейсы появляются по кнопке и в одном виде, а не у
каждого отдела по-своему; данные за них покупаются экономно — дорогие запросы
идут только по проектам-претендентам; и любое число на листе можно объяснить —
сервис показывает, из чего оно получилось.

Ниже — техническая шпаргалка для тех, кто работает с кодом.

---

Для того, кто возвращается после перерыва. Только факты из репозитория.

## 1. Что за сервис

Внутренний веб-сервис агентства: на вход — список проектов (домен, период
работ, ниша, гео, услуги, клиент, флаг «можно публиковать»), на выход — ZIP с
одностраничными PDF-кейсами по проектам с хорошим и средним результатом.
Путь: список (CSV/XLSX/Google Sheet) → сбор истории из Ahrefs → классификация
(`good` / `medium` / `poor` / `insufficient_data`) → кейс (А → Б, графики,
текст) → PDF → ZIP.

Стек: Python 3.12, FastAPI + Pydantic v2, PostgreSQL + SQLAlchemy 2 + Alembic,
Redis + RQ, фронт React 19 + Mantine + React Query + Vite, PDF — Jinja2 →
WeasyPrint, графики — SVG на бэкенде (один и тот же рисунок идёт в PDF и в веб).

| Часть | Где | Что делает |
|---|---|---|
| Ядро-библиотека | `src/ahrefs_cases/{intake,collect,classify,cases,export}/` | приём списка, сбор рядов и units, вердикты, структура кейса, HTML/PDF/ZIP |
| Хранилище | `src/ahrefs_cases/storage/` | проекты, серии, прогоны, версии порогов, вердикты, кейсы |
| Конфиг | `src/ahrefs_cases/config/` | типизированные настройки; `os.getenv` разрешён только здесь |
| API | `src/ahrefs_cases/api/` (`main.py`, `deps.py`, `security.py`, `routers/`) | FastAPI, JWT, права |
| Очередь | `src/ahrefs_cases/workers/main.py` | RQ-воркер, прогоны сбора и сборка кейсов |
| CLI | `src/ahrefs_cases/cli/` + `scripts/run_collect.py` | сквозной путь без веба |
| Фронт | `web/src/` (`pages/`, `api/`, `app/`, `auth/`) | загрузка, проекты, карточка, кейсы, пороги, прогоны, расход, люди |

## 2. Что в проекте особенного

- **Ядро не знает про веб.** Правило из `delivery/CONSTITUTION.md` (§Process
  principles, п. 7): сбор/классификация/сборка кейса — библиотека, FastAPI, RQ и
  React — обвязка. Стережёт `tests/test_core_isolation.py` плюс гейты
  `layers-gate` (import-linter / dependency-cruiser) и `service-no-web-gate`.
- **Провайдер Ahrefs `fixture` по умолчанию — везде, включая боевой компоуз.**
  Переключение в `live` — решение человека (HITL в конституции). Живой ключ в
  тестах запрещён: `tests/conftest.py` — «ни один тест не ходит в сеть и не
  берёт живой ключ».
- **Источник рядов называет вызывающий, умолчания нет** —
  `tests/test_source_is_required.py`: дважды умолчание давало чтение пустоты.
- **units — единственный платный ресурс.** Прогон не стартует, пока смета не
  сверена с остатком квоты (не узнали остаток — не тратим); закрытый месяц
  истории неизменяем, повторный сбор догружает только новое.
- **Канон домена — `knowledge/` (OKF 0.2).** Тронул код по пути из
  `implementation:` концепта — тронь концепт в той же поставке; прибито гейтом
  `scripts/okf_sync_gate.py`. Осознанный дрейф — строкой
  `canon_drift_waiver: reason=… by=human:…` в STATUS, а не правкой концепта.
- **Процесс поставок — `delivery/`.** Одна активная поставка:
  `delivery/active/{STATUS.md,tasks.md,decisions.md,diagnosis.md,verify-report.md}`;
  правила — `delivery/CONSTITUTION.md`; закрытые поставки уезжают в
  `delivery/archive/`. Порог поставки `max_loc_diff` = 800 строк, единица —
  два-три модуля, а не половина фазы (`AGENTS.md`).
- **Реестр находок — `docs/FINDINGS.md`:** что на фикстурах зелёное, а с живым
  ключом сломается по расчёту. Строка исчезает только после живого прогона или
  решения заказчика. Сверяться до того, как объявить готовым.
- **Уроки — `delivery/archive/INDEX.md`** (L1…): что узнали о системе, по путям
  репозитория; перед правкой найти строки, пересекающиеся с диффом.
- **Вариант D:** тексты канонов и клиентские документы (ТЗ, пороги заказчика,
  планы фаз) в git не уезжают — `.git/info/exclude`; механика коммитится.
  Проверка: `python3 extract_payload.py --check-local .` — оба числа нулевые.

## 3. Что закрыто оракулами

52 файла в `tests/` + 16 vitest-файлов в `web/src/**/__tests__/`. Тесты идут
против настоящего Postgres из дев-компоуза; сеть запрещается явно.

**Сбор и units**
- `test_collect_run.py` — сто доменов без сети, журнал units, короткая история.
- `test_collect_quota.py` — смета до первого запроса, fail-closed при неизвестном остатке, чужой резерв.
- `test_collect_cache.py`, `test_collect_single_flight.py` — инкремент от последней точки; одновременные запросы по домену склеиваются в один.
- `test_collect_scheme.py`, `test_collect_stage2_scheme.py`, `test_collect_case_step.py` — схема «точки А/Б против истории», выбор способа на каждый endpoint, докупка под графики.
- `test_collect_funnel.py` — за «плохих» дорогие метрики не платятся (проверка числом запросов).
- `test_collect_response_guard.py` — чужая форма ответа падает громко, а не выглядит как «у ста доменов нет истории».
- `test_collect_endpoints_live.py` — записанные показания живого ключа (12.09.2026), а не арифметика.
- `test_collect_resilience.py`, `test_collect_run_timeout.py`, `test_run_failure_reason.py` — предохранитель, реапер, чекпойнты, инвариант «лимит прогона vs. реапер», первая причина падения в журнале.
- `test_units_profile.py` — цена прогона в документе обязана совпадать с моделью (`scripts/units_profile.py`).

**Приём списка**
- `test_intake_normalize.py` (golden «вход → канонический хост»), `test_intake_sources.py` (CSV/XLSX/Sheet дают побайтово одинаковую таблицу), `test_intake_validate.py` (коды отказа — контракт с экраном), `test_intake_accept.py` (сто строк, повторная загрузка не удваивает).

**Классификация и пороги**
- `test_classify_rules.py` — границы правил на числах; `test_classify_golden.py` — таблица «сценарий генератора → группа» без базы и сети, на нейтральном `config/thresholds.default.yml`.
- `test_classify_verdicts.py` — вердикт хранит версию порогов, пороги из базы, ноль сетевых запросов.
- `test_classify_recalc.py`, `test_classify_preview.py` — пересчёт по версии, предпросмотр «кто сменит группу» без записи, нехватка купленных месяцев показана отдельно.
- `test_classify_coverage_agreement.py` — `classify`, `preview` и `recalc` отвечают об одном проекте одинаково.
- `test_classify_diagnose.py` — разбор «плохих».

**Кейсы, PDF и графики**
- `test_cases_builder.py` (числа из записанного вердикта, анонимность, детерминированность), `test_cases_narrative.py` (текст по числам, стоп-лист, запрет утверждений о работах), `test_cases_pdf.py` (одна страница, сноска и атрибуция, fail-closed), `test_cases_charts.py` (дыра не интерполируется, отметка старта, окна А и Б), `test_export_grouping.py` (свёртка в кварталы зависит от природы метрики), `test_cases_archive.py` (имена по ТЗ, состав ZIP, контент-запрет).

**API и права**
- `test_api_auth.py` (вход, одинаковый отказ, пустой секрет, правило прав в одном месте), `test_api_users.py` (личное право поверх группы, последний админ, пароль один раз), `test_api_thresholds.py`, `test_api_runs.py` (замок, inline-очередь, упавшая задача), `test_api_read.py`, `test_api_intake.py` (смета совпадает с планом, закрытая Google Sheet), `test_api_cases_pack.py`, `test_api_charts.py` (рисунок по HTTP совпадает с тем, что уходит в PDF), `test_health.py`.

**Фронт (`web/src/**/__tests__`, vitest)**
- `api/client.test.ts` — четыре исхода запроса (401/403/503 не сливаются).
- `app/nav.test.ts` — меню строится по правам, не по названию группы; `shell.test.tsx` — шапка на 400 px; `theme-toggle.test.tsx`.
- `auth/login.test.tsx`, `auth/session-expiry.test.tsx` — сессия, протухшая посреди работы.
- `pages/projects.test.tsx` («данных не хватает» ≠ «плохой», фильтры уходят на сервер), `card.test.tsx`, `cases.test.tsx`, `intake.test.tsx`, `ops.test.tsx`, `thresholds*.test.tsx` (разнесённость «сохранить / применить / пересчитать»), `users*.test.tsx` (происхождение права).

**Оракулы самого контура**
- `test_delivery_promises.py` — объявленный в STATUS `repro_test` обязан существовать.
- `test_core_isolation.py`, `test_cleanup_scope.py` (тест правит своё, а не таблицу), `test_backup_covers_state.py` (том в компоузе ↔ `scripts/backup.sh`), `test_migrations.py` (цикл upgrade → downgrade → upgrade, под флагом), `test_config.py`, `test_cli_exit_codes.py`, `test_probe_next_day.py`.
- `test_ci_gates_judge.py` — «гейт, который не судит, обязан быть виден»: у джобы со сьютом есть Postgres, сьют гоняется один раз, гейт покрытия печатает причину обрыва, область мутаций объявлена в `src/`, и отсрочка приговора истекает вслух.

**Гейты (`.pre-commit-config.yaml` + `scripts/lint/`)**
ruff / ruff-format / mypy strict; ESLint + warning-ratchet + Prettier; длина
файлов (prod ≤ 500, tests ≤ 1000, baseline-ratchet); grep-гейты `config-access`,
`di-indirection`, `service-no-web`, `no-grab-bag-module`, `blind-error`,
`unstructured-log`; AST-гейты `silent-except`, `inline-prompt`, `cpu-in-async`,
`unbounded-list`; `jscpd-dry-gate`, `layers-gate`, `complexity-gate`,
`detect-secrets-guard`, `deps-audit` (stage `manual`), `okf-validate` +
`okf-sync`, `gate-coverage` («каждый гейт-скрипт подключён»). Отдельно
`scripts/delivery_check.py` — фазовый гейт поставки, `scripts/merge_guard.sh`.

**Сейчас информационные, а не судящие** (см. `docs/FINDINGS.md`):
- **Diff coverage** (`MIN_PCT=70`) — `continue-on-error: true` в `.github/workflows/quality.yml`. Отсрочка со сроком **29.09.2026** из-за Z22: `cli/collect_commands.py` 39,3 %, `cli/case_commands.py` 41,3 %, `cli/source.py` 69,2 %. Числа печатаются каждый прогон; срок стережёт `test_the_coverage_waiver_expires_out_loud`. Закрывать поставкой `cli-commands-are-tested`.
- **Мутационный гейт** (Z20) — закрыт наполовину: область мутаций читается (`src/pyproject.toml`, ключ `source_paths`), мутации до тестов доходят, но вердикта нет — mutmut гоняет pytest из `src/mutants`, а сьют предполагает корень репозитория. Пока гейт честно молчит и выходит нулём.
- **Vulnerable dependencies (список, информационно)** — тот же приём в джобе `gates`.

## 4. Что поднято в докере

`docker-compose.dev.yml` (`name: ahrefs-cases-dev`), стадии `Dockerfile`:
`base` → `dev` / `prod`, `web-dev` / `web-build` → `web` (nginx).

| Сервис | Порт | Монтируется | Healthcheck |
|---|---|---|---|
| `postgres` (postgres:16-alpine) | 5432 | том `pgdata` | `pg_isready -U cases -d cases` |
| `redis` (redis:7-alpine) | 6379 | — | `redis-cli ping` |
| `migrate` (одноразовый, `alembic upgrade head`) | — | `src`, `migrations`, `alembic.ini` | — (`service_completed_successfully`) |
| `api` (uvicorn `--reload`) | 8000 | `src`, `migrations`, `config`, `scripts`, `templates`, `data` | `python -c urllib.request.urlopen('http://localhost:8000/api/health')` |
| `worker` (`python -m ahrefs_cases.workers.main`) | — | `src`, `config`, `scripts`, `templates`, `data` | — |
| `web` (vite dev) | 5173 | `./web` + том `web_node_modules` | — (ждёт `api` healthy) |

`QUEUE_BACKEND: redis` жёстко: `inline` в процессе сервера поднимает свой цикл
событий и рвёт соединения движка базы. **`AHREFS_PROVIDER: ${AHREFS_PROVIDER:-fixture}`
— берётся из окружения запускающего, умолчание компоуза `fixture`.** `AHREFS_API_KEY`
пробрасывается даже в фикстурном режиме: ряды идут из фикстур, а остаток квоты
принадлежит ключу и стоит 0 units.

Боевой `docker-compose.yml` (`name: ahrefs-cases`): исходники не монтируются,
фронт — сборка под nginx, API без `--reload`, база и Redis наружу не
опубликованы, секретов в файле нет (`${VAR:?…}` — не задал, компоуз не
стартует), фронт на `${WEB_PORT:-8080}`, тома `pgdata`, `redisdata`, `casedata`.
Провайдер и там `fixture` по умолчанию.

```bash
# поднять дев-стенд: http://localhost:5173 (фронт), http://localhost:8000 (API)
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml build          # только если менялись зависимости

# первый пользователь (пароль пустой → сгенерируется и покажется один раз)
docker compose -f docker-compose.dev.yml exec api \
    python scripts/run_collect.py useradd you@example.com admin

# CLI в контейнере: intake | collect | stage2 | classify | case-data | recalc |
# preview | cases | pack | render | diagnose | explain | all | useradd
docker compose -f docker-compose.dev.yml exec api \
    python scripts/run_collect.py all config/projects.example.csv

# пересобрать кейсы и сложить ZIP
docker compose -f docker-compose.dev.yml exec api python scripts/run_collect.py pack

# боевой запуск
POSTGRES_PASSWORD=... JWT_SECRET=... docker compose up -d --build   # http://localhost:8080

# тесты и гейты — на машине, не в контейнере (нужна дев-база из компоуза)
.venv/bin/python -m pytest -q
.venv/bin/python -m pre_commit run --all-files
```

## 5. Куда смотреть в первую очередь

| Файл | Зачем |
|---|---|
| `AGENTS.md` | правила проекта: что нельзя, где канон, размер поставки |
| `delivery/active/STATUS.md` | что делается прямо сейчас и чем это закрывается |
| `docs/FINDINGS.md` | что зелёное на фикстурах и сломается с живым ключом (Z-строки) |
| `delivery/archive/INDEX.md` | уроки L1… по путям репозитория — читать до правки |
| `knowledge/index.md` + `knowledge/references/repo-map.md` | канон домена и карта репозитория |
| `README.internal.md` | домен, слои, запуск, безопасность — одним документом |
| `delivery/CONSTITUTION.md` | product non-negotiables и что требует человека (HITL) |
| `scripts/run_collect.py` | весь сквозной путь одной командой, без веба |
| `docker-compose.dev.yml` | что из чего поднимается и чем проверяется |
| `.pre-commit-config.yaml` | полный список гейтов с объяснением каждого |
