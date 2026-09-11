# Active delivery status

- **slug:** web-cases
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай продолжим» — следующий экран Ф6 по согласованному порядку: кейсы со скачиванием)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=экран файлов не производит, а отдаёт собранные
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/CasesPage.tsx reason=скачивание проверяется исполнением: токен уходит заголовком, файл сохраняется из памяти вкладки — в jsdom этого пути нет вовсе
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** человек забирает кейс и пачку из браузера и видит, какие кейсы анонимизированы, то есть какие нельзя публиковать под именем клиента
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

`/cases` — заглушка, хотя API отдаёт и библиотеку, и файлы, и пачку (последнюю
с прошлой поставки). Экран закрывает единственный сценарий, ради которого
сервис существует: посмотреть, что собрано, понять, что из этого можно
публиковать под именем клиента, и забрать файлы.
