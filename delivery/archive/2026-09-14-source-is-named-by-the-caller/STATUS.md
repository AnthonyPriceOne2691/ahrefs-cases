# Active delivery status

- **slug:** source-is-named-by-the-caller
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_cli_exit_codes.py::test_every_reading_command_takes_the_source
- **diagnosis:** n/a reason=причина известна и записана как Z11: правило применили к трём командам вместо класса команд
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («давай по порядку» — Z11 первым пунктом)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none reason=запрет `Bash(AHREFS_PROVIDER=live:*)` возвращён владельцем 14.09.2026, коммит разблокирован (разбор — `escalation.md`)
- **new_dependency:** no
- **runtime_paths:** n/a reason=разбор аргументов и выбор источника, внешних вызовов нет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** пересчёт вердиктов по живым рядам не требует поднимать живой режим
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Z11. Поставка `read-bought-series-without-live` развела «откуда покупать» и «что
читать» — но только у трёх команд, которые тогда были под рукой: `cases`,
`render`, `pack`. Считающие команды — `classify`, `explain`, `preview`, `recalc`,
`diagnose` — остались брать источник из режима провайдера, хотя ни одна из них в
Ahrefs не ходит. Чтобы пересчитать вердикты по **уже купленным** живым рядам,
14.09.2026 пришлось поднять `AHREFS_PROVIDER=live`: снять предохранитель,
защищающий деньги заказчика, ради операции, которая ключом не пользуется.

Вторая половина поставки — про то, почему это не заметили. В STATUS той
поставки объявлен `repro_test`:
`tests/test_cli_exit_codes.py::test_reading_commands_take_the_source_explicitly`.
**Такого теста в репозитории нет.** Флаг работал, а держать его было нечему — и
класс команд целиком остался за границей проверки. Объявленный оракул, которого
не существует, хуже отсутствующего: он закрывает вопрос, не отвечая на него.
