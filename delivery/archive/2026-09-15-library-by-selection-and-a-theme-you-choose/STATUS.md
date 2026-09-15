# Active delivery status

- **slug:** library-by-selection-and-a-theme-you-choose
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** web/src/pages/__tests__/cases.test.tsx
- **diagnosis:** n/a reason=две названные владельцем возможности; попутный дефект темы разобран в decisions
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 15.09.2026)
- **human_ok_spec:** yes at=2026-09-15 by=human:anthony («в кейсы нужно добавить чек боксы… либо один, либо несколько, либо все pdf»; «сделай переключатель темы, расположи слева внизу — значком»)
- **human_ok_plan:** n/a reason=два независимых экранных куска, каждый в своих файлах
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файлы собирает прогон сборки, эта поставка их только отдаёт
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=правка экранов и оформления; ручка выдачи выборки заведена прошлой поставкой
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** из библиотеки забирается выборка кейсов одним движением; выбранная тема переживает перезагрузку и держится на всех экранах
- **observe_until:** 2026-09-29
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Две возможности, названные владельцем, и один дефект, найденный по дороге.

**Отметки в библиотеке кейсов.** Скачать можно было по одному. Отправить
клиенту десять означало десять походов к таблице. Теперь строки отмечаются;
несколько уезжают одним архивом, один — файлом, а не архивом из одного файла.

**Переключатель темы.** Его не было вовсе: тема бралась из настройки ОС
(`defaultColorScheme="auto"`), и сменить её из сервиса было нельзя.

**Дефект, найденный при этом:** тёмные правила `glass.css` висели на
`@media (prefers-color-scheme: dark)`, а Mantine ставит `data-mantine-color-scheme`
на `<html>`. Переключатель, добавленный поверх такой разметки, применялся бы
наполовину: у человека с тёмной системой ручной выбор «светлая» дал бы светлые
компоненты поверх тёмного полотна и почти белые чернила. То есть до этой
поставки светлая тема была не «непроверенной», а нерабочей при ручном выборе —
и узнать это можно было, только заведя сам переключатель.
