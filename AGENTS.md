# Ahrefs Cases — инструкции агенту

Сервис автоматической генерации SEO-кейсов из динамики Ahrefs. Клиентский проект;
репозиторий передаётся компании.

## Canon stack / Agent Delivery Harness

- **Start here:** `AGENT_STACK.md` (order: Delivery → CQG → OKF).
- Process canon: `AGENT_DELIVERY_HARNESS.md`.
- Active delivery: `delivery/active/STATUS.md` — read before coding.
- **Order:** follow delivery phases. Do not oneshot large work.
- **Done:** only when verify oracles pass; never declare done on red.
- Prefer git worktree for class M/L (Delivery §5.1).
- Smoke/evals: `delivery/evals/smoke/` + `active/eval-smoke.md` (Delivery §6).
- Metrics on handoff: Delivery §9 / A.10.
- Hooks if deployed: Delivery §10.
- Skills/prompts: `skills/README.md` (Delivery §11); no inline prompts (CQG).
- Do **not** duplicate code-quality rules here — use `CODE_QUALITY_GATES.md` if present.
- Do **not** invent domain canon — use `knowledge/` / OKF if present.
- Deploy order for missing layers: Delivery → CQG → OKF (see `AGENT_STACK.md`).

## Контур развёрнут волнами

Развёрнуты волны В0 (① Delivery), В1 (② CQG + CI + гейт мержа) и В2 (③ OKF,
11.09.2026). Не развёрнута В3 (⑤ оракулы поведения модели) — ждёт первого
вызова модели. Триггеры и предельные сроки —
`docs/CONTOUR_ROLLOUT.md`. Состояние осей — в `delivery/active/STATUS.md`, и оно
записано честно: `weak` там не забывчивость, а объявленный пробел.

**Вариант D:** тексты канонов (`AGENT_*.md`, `CODE_QUALITY_GATES.md`,
`OKF_KNOWLEDGE_BUNDLE.md`, `stack_selftest.py`, `selftest_sizes.py`,
`extract_payload.py`) лежат локально и в git не уезжают — `.git/info/exclude`.
Механика (`scripts/**`, `delivery/**`, конфиги, workflow) коммитится: без коммита
она не может отклонить.

## OKF knowledge bundle

Канон домена — `knowledge/` (OKF 0.2). **Перед догадками из памяти по
каноническим вопросам** — что определяет группу, сколько стоит запрос, какой
схемой собирать историю, где в репозитории что лежит — открывай
`knowledge/index.md` и спускайся по разделам.

Парная вещь к `delivery/archive/INDEX.md`: индекс архива отвечает «на чём мы
уже спотыкались в этом модуле», карта репозитория
(`knowledge/references/repo-map.md`) — «как этот репозиторий вообще устроен».

Правило записи: тронул код по пути из `implementation:` концепта — тронь
концепт в той же поставке. Это прибито гейтом `okf_sync_gate.py`. Смысл не
менялся (типы, формат, переименование) — строка
`canon_drift_waiver: reason=… by=human:…` в STATUS активной поставки, а **не**
правка концепта «чтобы позеленело».

## Реестр находок

`docs/FINDINGS.md` — что известно про продукт: заведомо неработающее в живом
режиме, гипотезы под расчётами, ограничения метода, объявленные границы и
чего ждём от заказчика. Ведётся по ходу; строка исчезает только когда
проверена живым прогоном или закрыта решением заказчика.

Перед тем как объявить что-либо готовым, сверься с разделом 1: там то, что
на фикстурах зелёное, а с ключом сломается по расчёту.

Отдельно: `docs/UNITS_OPTIMIZATION.md` — разведка показала, что биллинг
Ahrefs построчный, и нынешняя схема сбора стоит в восемь раз больше бюджета
заказчика. Там расчёт и предлагаемая схема в три ступени.

Спутники реестра: `docs/PHASE7_CHECKLIST.md` (что проверить первым живым
ключом — по пунктам, с ожидаемыми значениями и действиями при расхождении) и
`docs/CALIBRATION_QUESTIONS.md` (что решает заказчик на калибровке).

## Размер поставки

**Поставка — два-три модуля, а не половина фазы.** Порог `max_loc_diff` = 800
строк остаётся; фазы `docs/PHASES_V3.md` режутся на поставки так, чтобы в него
попадать. Правило принято 10.09.2026 после двух превышений подряд (Ф2б — 2521,
Ф3а — 1584, обе под waiver): если предохранитель срабатывает каждый раз, он
перестаёт быть сигналом.

Практически это значит: перед `specify` прикинь объём и режь заранее, а не
дописывай пришедшее требование в открытую поставку (урок L15).

## Что нельзя делать в этом проекте

- **Переключать провайдера Ahrefs в `live`.** Разработка идёт на `AHREFS_PROVIDER=fixture`:
  записанные и синтетические ответы, без сети и без расхода квоты. Живой ключ жжёт
  units заказчика — переключение решает человек.
- **Класть клиентские документы в git.** ТЗ, план фаз, оценки, пороги и внутренние
  разборы перечислены в `.git/info/exclude` и остаются локально. Проверка:
  `python3 extract_payload.py --check-local .` — оба числа должны быть нулевыми.
- **Писать `os.getenv` вне `src/ahrefs_cases/config/`.** Конфиг типизированный,
  доступ только через `config.X`.
- **Молча глотать ошибки.** Каждый `except` — либо лог с контекстом, либо `raise`.

## Ориентиры

| Что | Где |
|---|---|
| Документ реализации (архитектура, модель данных, экраны) | `docs/IMPLEMENTATION_V3.md` (локальный) |
| Фазы Ф1–Ф9 с критериями готовности | `docs/PHASES_V3.md` (локальный) |
| ТЗ заказчика и его ответы | `docs/SPEC_FROM_SHEET.md` (локальный) |
| Экономия units — приёмы и обоснование | `docs/UNITS_ECONOMY.md` (локальный) |
| Ahrefs API v3: endpoint'ы и стоимость | `docs/RESEARCH_AHREFS_API.md` |
