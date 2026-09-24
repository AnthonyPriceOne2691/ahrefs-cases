# Active delivery status

- **slug:** transport-obeys-retry-after
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_collect_transport.py::test_retry_after_is_obeyed_instead_of_our_ladder
- **diagnosis:** n/a reason=причина известна и записана как Z14: заголовок не читается вовсе
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026 — «давай z12 и так далее»)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («давай дальше что осталось» — Z14 следующий и чинится без ключа)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/collect/ahrefs_transport.py reason=сам 429 живым ключом выжать не удалось (75 запросов, 40 параллельно — ни одного), поэтому правило проверяется подставным ответом, а встретится впервые в бою
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** в журнале прогона видно, что пауза после 429 взята из ответа Ahrefs, а не из нашей лесенки
- **observe_until:** 2026-10-08 (сдвинут 24.09.2026: до выкладки PR #7 прода не было — наблюдать было негде; окно отсчитано от выкладки, +14 дней. Сигнал про живые данные наблюдаем только после перевода в live — это решение владельца; не переведут к сроку — сдвиг с той же причиной)
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Z14. Транспорт повторяет 429 по собственной лесенке пауз
(`AHREFS_RETRY_BACKOFF_SEC` = 1, 5, 30 с) и заголовок `Retry-After` не читает
вовсе. Если Ahrefs просит подождать дольше, все три попытки сгорают внутри окна
запрета: домен уходит в `failed`, а серия таких падений поднимает
предохранитель и останавливает **весь прогон**. На сотне доменов это потерянный
прогон, а не потерянный домен.

Замер 14.09.2026 показал, что выжать 429 не удаётся (75 бесплатных запросов, до
40 параллельно — ни одного отказа, и заголовков `x-ratelimit-*` Ahrefs не шлёт).
Значит величину паузы мы не знаем и узнаем её впервые в бою — правило обязано
работать при любой.
