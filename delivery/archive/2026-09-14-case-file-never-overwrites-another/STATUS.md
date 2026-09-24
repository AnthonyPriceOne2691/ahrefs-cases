# Active delivery status

- **slug:** case-file-never-overwrites-another
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_cases_pdf.py::test_second_case_of_the_same_niche_does_not_overwrite_the_first
- **diagnosis:** n/a reason=причина известна: правило разведения имён есть только у архива
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026 — «давай поправим дефекты»)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («давай поправим дефекты»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** case-pdf reason=дефект виден именно на диске: файл есть, а кейса в нём нет
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=запись файла на диск, внешних вызовов нет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** в `data/out/` столько файлов, сколько собрано кейсов, и ни один не затёрт
- **observe_until:** 2026-10-08 (сдвинут 24.09.2026: до выкладки PR #7 прода не было — наблюдать было негде; окно отсчитано от выкладки, +14 дней. Сигнал про живые данные наблюдаем только после перевода в live — это решение владельца; не переведут к сроку — сдвиг с той же причиной)
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Имя файла по ТЗ — «название сайта + Кейс», а у непубличных — «сайт в нише X +
Кейс». Значит два анонимных кейса одной ниши дают **одно и то же имя**. Архив
это разводит (`_unique`), а `render_pdf` пишет по имени как есть: второй кейс
молча затирает первый, и на диске остаётся файл, в котором лежит чужой проект.

После поставки `campaigns-of-one-domain-pay-once` случай стал шире: две
кампании одного сайта дают одинаковый заголовок и без всякой анонимности.

Правило разведения имён при этом уже написано — просто живёт в архиве, то есть
в одном из двух путей выдачи. Ровно тот класс, что L142.
