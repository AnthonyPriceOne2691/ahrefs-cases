# Tasks: cases-stage-journal

Уроки по затронутым путям — в `plan.md`: **L130**, **L13**, **L125**, **L85**,
**L88**, **L63**, **L214**, **L185**, **L184**, **L120**, **L12**, **L5**,
**L140**, **L150**, **L217**, **L57**, **L8**, **L68**, **L79**, **L211**,
**L64**, **L170**, **L223**, **L142**, **L221**, **L222**; не применимы по
существу — **L27**, **L40**, **L151**, **L152**, **L133**, **L141** и уроки
путей #27 (почему — там же).

- [x] Y1–Y3, Y7–Y9: `tests/test_cases_journal.py`; Y4 — `tests/test_cases_builder.py`;
      Y5 — `tests/test_collect_run.py`; Y6 — `ops.test.tsx`. Y1 красный до правки
      по причине дефекта (`projects_ok` 0, судеб нет).
- [x] Исходы ступени кейсов в `storage/_enums.py`, миграция, `cache.empty_since`.
- [x] `cli/case_commands.py`: `pack_built`, `CasePack`, `case_fates`;
      `export/archive.py`: запрещённые кейсы в `EmptyArchiveError`, `cases_inside`.
- [x] `workers/jobs._pack`: судьбы, число проектов, `finish_run`, сводка в лог.
- [x] `cases/builder.py`: совет по рядам вердикта, `project_id` у каждой попытки.
- [x] `api/routers/alerts.py`: пачка и число кейсов в ней.
- [x] Экран: слова исходов (`status.ts`), «не положен по группе» числом (`RunFates.tsx`).
- [x] Канон: `case-content.md`, `data-coverage.md`, `knowledge/log.md`.
- [x] pytest на своей копии базы (725 passed, 3 skipped), vitest (202), mypy,
      ruff, tsc, eslint, prettier; цикл миграции на копии с данными и с нуля.
- [x] Исполнение Y10: копия дев-базы, воркер RQ, журнал через API и экран в
      Chrome, до и после; копии, каталоги и процессы убраны.
- [x] Handoff: verify-report, `docs/FINDINGS.md` Z46, архив, уроки L219–L220.
- [ ] Подпись проверяющего (human:anthony) под verify-report.
