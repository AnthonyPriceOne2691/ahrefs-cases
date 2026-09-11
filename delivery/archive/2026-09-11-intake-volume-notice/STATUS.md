# Active delivery status

- **slug:** intake-volume-notice
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_intake_validate.py::test_text_volume_keeps_the_project
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай возьмем первый» — не ронять строку из-за объёма работ, ячейку показывать замечанием)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=поведение проверяется тестами приёма; экран уже прогнан живым файлом
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** первая настоящая таблица отдела принимается, а непонятые ячейки объёма видны отдельным списком; проект не пропадает из-за подписи «214 ссылок»
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Найдено прогоном живого экрана 11.09.2026: таблица из десяти годных проектов
отклонилась целиком, потому что в колонке «объём работ» стояло «214 ссылок», а
не «214».

Несоразмерность видно по сравнению двух строк: **пустая ячейка проходит, а
заполненная словами выбрасывает весь проект**. Строка с меньшей информацией
принимается, строка с большей — нет, хотя домен, период и гео у неё в порядке.
