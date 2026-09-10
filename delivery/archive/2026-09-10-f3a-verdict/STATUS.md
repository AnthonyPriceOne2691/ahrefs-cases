# Active delivery status

- **slug:** f3a-verdict
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление живёт в `delivery/STACK-ACCEPTANCE.md` (урок L16)
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes (by=human:anthony, at=2026-09-10) — спека D1–D13 подписана до кода (коммит 44c9bd8); D14–D20 дописаны по ходу и подписываются отдельно на verify
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
- **waivers:** max_loc_diff=1600 reason=поставка написана до принятия нового правила о размере; 1584 строки, из них ~800 тесты. Правило «резать фазы на поставки по 2–3 модуля, порог 800 остаётся» принято по итогам двух превышений подряд и применяется со следующей поставки (Ф3б). Урок L17 в archive/INDEX.md by=human:anthony
- **new_dependency:** none reason=расчёт на существующих таблицах и PyYAML из Ф1
- **runtime_paths:** none reason=классификация не ходит в сеть по построению; это проверяется тестом, а не обещанием
- **model_surface:** n/a reason=в MVP текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `python3 scripts/run_collect.py classify` даёт распределение по четырём группам, а `explain example.com` — шесть условий с фактами и порогами, где `good.supporting_required` = 2 из 1. Пропажа объяснения или группа без сработавших условий означает, что правила разъехались с порогами
- **observe_until:** 2026-09-24
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
