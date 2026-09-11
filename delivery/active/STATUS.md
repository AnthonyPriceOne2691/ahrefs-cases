# Active delivery status

- **slug:** cases-pack-api
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony (выбран вариант «да, с пачкой»: выдача ZIP по HTTP входит в работу над кейсами)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** pack-download reason=роутер отдаёт человеку файл пачки, и тест сверяет, что отдан именно он, байт в байт
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/api/routers/cases.py reason=выдача файла проверяется исполнением: каталог выгрузки живёт в контейнере, и «пачка есть» — вопрос к диску, а не к базе
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** пачку кейсов забирают по HTTP, а не `docker cp` с сервера
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Пачка ZIP — выход сервиса по ТЗ. Собрать её можно прогоном
(`POST /api/runs/cases`), а забрать нельзя ничем, кроме доступа к диску
контейнера: по HTTP её не отдаёт никто.

Поставка закрывает выдачу: состояние пачки и сам файл. Экран, который это
покажет, — следующая поставка; порядок такой, потому что первая половина
проверяется без интерфейса и с ней уже можно работать курлом.

## Почему поставка разрезана

Экран кейсов и выдача пачки вместе дали 988 строк при пороге 800. Резать по
границе работ, а не просить waiver — правило, выведенное уроком L50: «бэк
отдаёт файл» и «экран показывает библиотеку» проверяются по отдельности и
разными оракулами.
