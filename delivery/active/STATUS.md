# Active delivery status

- **slug:** f3a-verdict
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление живёт в `delivery/STACK-ACCEPTANCE.md` (урок L16)
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** pending — спека D1–D13 написана и коммитится ДО кода
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=поставка не производит файловых артефактов; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
  <!-- Формула нормализации на длительность от заказчика не пришла, но Ф3а её
       не требует: блок вынесен в Ф3б целиком, а не заведён выключенным. -->
- **waivers:** none
- **new_dependency:** none reason=расчёт на существующих таблицах и PyYAML из Ф1
- **runtime_paths:** none reason=классификация не ходит в сеть по построению; это проверяется тестом, а не обещанием
- **model_surface:** n/a reason=в MVP текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Границы: почему Ф3 разрезана до начала работ

Урок L15 из Ф2б: требование, пришедшее в середину поставки, дописали в неё
вместо пересмотра границ — 2521 строка при пороге 800 и класс L под waiver.
Здесь граница проведена заранее: Ф3а даёт **вердикт** (точки, дельты, пороги,
группы, объяснение), Ф3б — **работу с порогами и диагностику** (пересчёт по
версии, предпросмотр смены группы, разбор «плохих», нормализация на
длительность, когда придёт формула).

## Волна контура В2 идёт после Ф3, а не перед

Триггер В2 (③ OKF) — «инварианты домена перестали меняться каждый день:
группы, пороги, правила экономии units зафиксированы в коде и тестах»
(`docs/CONTOUR_ROLLOUT.md`). До конца Ф3б пороги ещё двигаются, канонизировать
нечего. Предельный срок — начало Ф8: при калибровке правка порога начнёт
ломать golden-таблицы, и ратчет нужен до, а не после. Там же сказано, что
волна разворачивается **отдельной сессией**, не вперемешку с фичами.
