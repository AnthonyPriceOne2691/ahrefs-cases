# Tasks: two-campaigns-two-cases

Уроки по затронутым путям — в `plan.md`: **L150**, **L153**, **L180**, **L93**,
**L49**, **L138**, **L41**, **L139**, **L140**, **L8**, **L68**, **L79**,
**L211**; не применимы — **L151**, **L152**, **L43**, **L88**, **L89**, **L92**, **L40**, **L46**, **L50**, **L57**, **L131**
(почему — там же).

- [ ] W1–W5: `tests/test_cases_pack.py` — красные на `origin/main` по причине
      дефекта (W1: в архиве один PDF вместо двух).
- [ ] `export/archive.py`: вход `ToPack`, `project_id` в `PackedCase` и
      `SkippedCase`; `tests/test_cases_archive.py` — на новом входе.
- [ ] `cli/case_commands.py`: номер сборки, строка `cases` и файл — по проекту.
- [ ] `cases/builder.py`: порядок кампаний одного сайта — по началу периода.
- [ ] Канон: `knowledge/product/case-content.md` (правило 19б), `knowledge/log.md`.
- [ ] pytest на своей копии базы, mypy, ruff; pre-commit на коммитах.
- [ ] Исполнение W6: копия дев-базы, пачка до и после правки, ZIP, `кейсы.csv`,
      sha256 против `case_artifacts`; копии и каталоги удалены.
- [ ] Handoff: verify-report (дайджест, ревью рисковых мест, исполнение,
      метрики), `docs/FINDINGS.md` Z39 → «Исправлено», архив, уроки L217–L218.
- [ ] Подпись проверяющего (human:anthony) под verify-report.
