# Tasks: usage-counts-live-units-only

Уроки по затронутым путям — в `plan.md`: **L116**, **L117**, **L115**,
**L191**, **L87**, **L8**, **L68**, **L79**, **L80**, **L58**.

- [x] R1, R2: `tests/test_api_usage.py` — R1 красный на `main` по причине дефекта (`assert 28066 == 27366`).
- [x] `collect/budget.py`: предикат `_live_run()`, каркас вопроса к строкам `SPENT`, `spend_summary`.
- [x] `api/routers/usage.py` зовёт `spend_summary`; `UsageView`: `conditional`, `live_domains`.
- [x] Знаменатель — домены, оплаченные живьём (уточнение координатора: удаление проектов готовится параллельно).
- [x] R3–R5, R8–R10: `tests/test_budget_spend.py`.
- [x] Экран: `types.ts`, `UsageTotals.tsx`; R6, R7 в `ops.test.tsx` — красные до правки.
- [x] Канон: `knowledge/ops/first-live-run.md`, `knowledge/log.md`.
- [ ] pytest, vitest, mypy, ruff, tsc, eslint, prettier; pre-commit по дифу.
- [ ] Исполнение: копия дев-базы, API до и после правки, экран в headless Chrome, SQL против экрана; копия удалена, процессы остановлены.
- [ ] Handoff: verify-report (дайджест утверждений, ревью рисковых мест, исполнение, метрики), `docs/FINDINGS.md` Z38, архив и урок в `INDEX.md`.
