# Active delivery status

- **slug:** f3b-recalc
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** pending — спека E1, E4–E7, E9, E10 коммитится до кода
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=пересчёт на существующих таблицах и правилах Ф3а
- **runtime_paths:** none reason=пересчёт не ходит в сеть; проверяется падающим httpx
- **model_surface:** n/a reason=текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Почему это идёт первым из оставшегося

Калибровка (Ф8) — самый рискованный из оставшихся этапов: она ждёт от
заказчика 10 доменов с экспертной оценкой и упирается в сроки. Без пересчёта
она невозможна в принципе. Сделать инструмент заранее — значит, когда материалы
придут, сесть и калибровать, а не начать писать.

Шаг 2 точками (экономия 561 unit на кандидата) идёт следующим: деньги нужны на
живом прогоне Ф7, а он и так ждёт боевого лимита от заказчика.

## Границы и дробление

Резано заранее, по правилу размера: здесь пересчёт и активация версии,
предпросмотр — следующей поставкой. Вчерашний замер показал, что 43 % диффа в
этом проекте — докстринги, поэтому «два модуля» и «800 строк» расходятся; режем
по модулям и проверяем числом.
