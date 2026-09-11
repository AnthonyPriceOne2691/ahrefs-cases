# Active delivery status

- **slug:** cases-latest-version
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_api_read.py::test_library_shows_one_case_per_project
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** n/a reason=класс S
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/api/routers/cases.py reason=дефект найден прогоном живого экрана, не тестом: шесть проектов дали пятьдесят строк
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** библиотека отвечает «какой файл отправить клиенту» одной строкой на проект; история доступна тумблером
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Пересборка кейсов добавляет версию, не затирая прежнюю. За девять сборок шесть
проектов дали пятьдесят строк библиотеки: версии 9, 8, 7 одного домена шли
вперемешку с соседними. На сотне доменов первая страница досталась бы двум-трём
проектам, а нужный кейс пришлось бы искать глазами.

Библиотека отвечает на вопрос «какой файл отправить клиенту» — значит по
умолчанию показывает свежий кейс каждого проекта. История остаётся: тумблер
«показать все версии» просит её у сервера.
