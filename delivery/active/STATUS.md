# Active delivery status

- **slug:** collect-case-step
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («делаем наиболее оптимальный вариант, сохранить полную информативность графика и цифр при рациональной экономии»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=PDF и ZIP собираются в Ф4; здесь только данные под них
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=две новые спеки endpoint'ов на существующей модели стоимости
- **runtime_paths:** src/ahrefs_cases/collect/plan.py, src/ahrefs_cases/collect/cache.py reason=докупка середины проверяется только исполнением: кэш по watermark считает такую серию собранной; доказательство — сквозной прогон ступени на фикстурах
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** yes reason=snapshot дублей поднят с 0 до 1: `collect_stage2` и `collect_case_data` — две публичные точки входа с одинаковой сигнатурой по построению (split-facade, случай назван самим гейтом). Тело у них общее (`_run_by_ids`), совпадает только список параметров; схлопывать их в одну функцию со ступенью-числом значило бы вынести магическое число в публичный API. Настоящий дубль из этой же поставки (фильтр окна в `cache.py`) вынесен в `_in_window`, а не переснят by=human:anthony
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Кейс показывает кривые, а вердикт — две точки. До сих пор мы покупали данные под
вердикт; здесь появляется ступень, которая докупает то, что **показывают**, и
только тем, у кого кейс будет.

Рычаг, которым не пользовались ни разу, — **состав полей**. Цена строки это
`10 × число биллингуемых полей + 1`, и у `keywords-history` их пять. Графику
нужны две корзины (топ-3 и топ-10), остальные три живут в кейсе числами на
границах периода — а границы уже куплены шагом 2.
