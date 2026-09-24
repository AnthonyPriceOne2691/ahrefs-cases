# Active delivery status

- **slug:** two-campaigns-two-cases
- **stack:** delivery@1.92, cqg@2.33, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_cases_pack.py::test_two_campaigns_get_two_files
- **diagnosis:** active/diagnosis.md
- **phase:** tasks
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-24 by=human:anthony (одобрен пункт «Две кампании — два PDF»; из задания: «Нужно: у каждой кампании свой кейс со своими данными, свой файл и своя строка в `кейсы.csv`. Имя файла — «домен + Кейс + номер сборки» (правило 18 …), разведение одинаковых имён — правило 18а (`pdf_renderer.unique_name`)»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** tests/test_cases_pack.py reason=дефект виден в собранном: в архиве один PDF на две кампании, а строки `cases` ссылаются на один файл; тест распаковывает ZIP и сверяет его с базой
- **ci-oracles:** tooling
- **worktree:** .claude/worktrees/agent-afac83d6310fad99c (ветка `bugfix/two-campaigns-two-cases` от `origin/main`; параллельно в соседнем worktree идут «мелочи журнала»)
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/cli/case_commands.py reason=сборка пачки по настоящей базе: две кампании `nordvpn.com`, две запрещённые `zeta-clinic.example`, порядок строк Postgres и файлы в каталоге выгрузки видны только исполнением на копии дев-базы, тест видит свои две строки
- **irreversible_surfaces:** none reason=автомерж в репозитории выключен, каждый PR сливает человек; выкатка в прод — ручная, по `docs/PROD.md`; проверка идёт на копии дев-базы и в каталоге выгрузки scratchpad, которые удаляются после проверки
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** —
- **observe_until:** —
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Пачка кейсов опознавала собранный кейс доменом: у сайта с двумя хорошими или
средними кампаниями в ZIP попадал один PDF, а обе строки `cases` получали
данные одной кампании и один файл (Z39). Ключ становится проектом во всех
трёх местах `pack_cases`, `pack` отдаёт номер проекта в каждом исходе, а
порядок кампаний одного сайта фиксирован началом периода.
