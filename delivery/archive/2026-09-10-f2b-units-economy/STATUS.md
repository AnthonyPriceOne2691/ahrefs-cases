# Active delivery status

- **slug:** f2b-units-economy
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D: текстов канонов в репозитории нет по построению
  <!-- Поле, а не проза: урок L7 из Ф2а. CI ищет эту строку grep'ом. -->
- **class:** L
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes (by=human:anthony, at=2026-09-10) — спека C1–C10 подписана; закоммичена отдельным коммитом 25ce154 ДО первой строки кода, порядок виден в истории
- **human_ok_plan:** yes (by=human:anthony, at=2026-09-10) — класс поднят до L вместе с waiver по объёму, план подписан задним числом вместе с ним
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=поставка не производит файловых артефактов; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** max_loc_diff=2600 reason=поставка открывалась как C1–C10 (экономия units), а по ходу получила C11–C18 — реапер, обработку ошибок, чекпойнты, предохранитель и память о пустом ответе, пришедшие по указанию заказчика работ и по итогам сверки с CRM. Это класс L, и резать надо было в момент прихода требований, а не дописывать блок; урок вынесен в archive/INDEX.md by=human:anthony
- **new_dependency:** none reason=кэш на существующих таблицах, single-flight на asyncio
- **runtime_paths:** network:api.ahrefs.com reason=preflight квоты — единственный новый сетевой путь; в fixture-режиме отвечает заглушка, в тестах сеть запрещена
- **model_surface:** n/a reason=в MVP текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** два прогона подряд одной командой: первый `сделано 3, потрачено 150`, второй `сделано 0, сэкономлено 3, потрачено 0`. Ненулевой расход на втором прогоне означает, что кэш или его граница месяца поехали
- **observe_until:** 2026-09-24
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Чем эта поставка отличается от Ф2а

Ф2а строила путь, Ф2б делает его дешёвым. Главный DoD всей Ф2 — «повторный
прогон не делает повторных запросов» — проверяется именно здесь, и это причина,
по которой фаза резалась надвое: тест на экономию не должен стоять на коде,
написанном в той же поставке.
