# Active delivery status

- **slug:** quota-is-asked-of-the-key-not-the-mode
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_api_intake.py::test_quota_source_follows_the_key_not_the_series_mode
- **diagnosis:** n/a reason=причина найдена чтением `build_quota` и подтверждена числом на экране: «Остаток квоты: 10 000» при настоящем остатке около 1,46 млн
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-15 by=human:anthony («по моему там не все цифры отражают нужную информацию»; выбор «Спрашивать ключ всегда»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** остаток units спрашивается у Ahrefs при каждом открытии сметы — бесплатный `subscription-info`; исполнено прогоном сьюта без ключа (учебный источник) и чтением ветки отказа (`quota.py:163`, переход в «остаток неизвестен»)
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на стенде смета показывает остаток ключа (сотни тысяч), а не 10 000
- **observe_until:** 2026-09-29
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

**Смета показывала учебное число как настоящий остаток.** Источник остатка
выбирался по режиму рядов: фикстурные ряды — `FixtureQuota` с зашитыми 10 000.
На стенде это и стояло в строке «Остаток квоты», при настоящем остатке ключа
около 1,46 млн. По этой строке человек решает, запускать ли прогон.

Признак теперь — **наличие ключа**, а не режим рядов: запрос остатка бесплатен
(`subscription-info`), а без ключа в сеть ходить нельзя вовсе.

**Правка вскрыла дыру в тестах.** Докстрока `tests/conftest.py` обещает: «ни
один тест не ходит в сеть и не берёт живой ключ Ahrefs». Обещание держалось
только на том, что источники сверялись с `provider`: стоило источнику
перестать это делать, как полтора десятка тестов пошли в сеть с боевым ключом
из `.env` — 16 падений и 15 ошибок. Ключ теперь снимается в `conftest` жёстко.
