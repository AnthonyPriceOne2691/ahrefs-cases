# Active delivery status

- **slug:** f3b-recalc-preview
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** pending — спека E1–E8 коммитится до кода
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
  <!-- Цель поставки — уложиться в порог 800 без waiver: это первая поставка
       по новому правилу (два-три модуля вместо половины фазы, урок L20). -->
- **new_dependency:** none reason=пересчёт на существующих таблицах и правилах Ф3а
- **runtime_paths:** none reason=пересчёт и предпросмотр не ходят в сеть; проверяется тестом
- **model_surface:** n/a reason=текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Первая поставка по новому правилу размера

Ф2б (2521 строка) и Ф3а (1584) прошли под waiver. Правило из `AGENTS.md`:
единица поставки — два-три модуля. Здесь их два — `classify/recalc.py` и
`classify/preview.py` — плюс две подкоманды CLI и тесты. Если и она выйдет за
800, значит проблема не в размере фаз, а в самом пороге, и это будет видно
на третьем случае подряд, а не по ощущению.
