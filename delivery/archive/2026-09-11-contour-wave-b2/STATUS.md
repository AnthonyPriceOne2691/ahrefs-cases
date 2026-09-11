# Active delivery status

- **slug:** contour-wave-b2-okf
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** chore
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («добьём Ф3 и В2» — состав волны задан docs/CONTOUR_ROLLOUT.md и OKF_KNOWLEDGE_BUNDLE.md §5)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=валидатор и гейт синхронизации на стандартной библиотеке
- **runtime_paths:** none reason=правка касается канона знаний и двух гейтов; оба проверяются собственным прогоном
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `okf_validate` даёт 0 ошибок на 16 файлах bundle'а; `okf_sync_gate` краснеет на правке кода по пути из `implementation:` без правки концепта и зеленеет вместе с ней; оба хука видны в `gate-coverage`; CI зелёный и на push в main, и на PR-потоке
- **observe_until:** 2026-09-25
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Почему волна пришла именно сейчас

Триггер из `docs/CONTOUR_ROLLOUT.md`: «инварианты домена перестали меняться
каждый день». Ф3 закрыта — группы, пороги, точки А/Б, модель стоимости и схема
сбора зафиксированы кодом и тестами. Предельный срок волны — **начало Ф8**, и
причина названа там же: при калибровке правка порога будет ломать golden-таблицы,
и снимок захочется перезаписать вместо того, чтобы удовлетворить. Ратчет нужен
**до** калибровки, а не после.

Preflight §0 выполнен 11.09.2026: upstream SPEC прочитан, версия `0.2` совпала с
pinned в каноне — правки канона не потребовалось.
