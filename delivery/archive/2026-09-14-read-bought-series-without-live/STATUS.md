# Active delivery status

- **slug:** read-bought-series-without-live
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** chore
- **repro_test:** tests/test_cli_exit_codes.py::test_reading_commands_take_the_source_explicitly
- **diagnosis:** n/a reason=не дефект: недостающая возможность, замеченная при сборке кейсов
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («сохрани этот кейс», «погоняй ещё кейсы» — для этого нужно читать уже купленные живые ряды)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** case-pdf reason=проверяется собранным кейсом на живых рядах
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=чтение базы, внешних вызовов нет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** кейс по живым данным собирается, не переключая провайдера в live
- **observe_until:** 2026-09-28
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Чтобы собрать кейс по **уже купленным** живым рядам, приходилось переключать
провайдера в `live` — то есть снимать запрет, который защищает деньги
заказчика. Между «откуда покупать» и «что читать» разницы не было, хотя это
разные вопросы: чтение базы не делает ни одного запроса к Ahrefs.

Практическое следствие сегодня: собрать кейс по калибровочным доменам нельзя,
не открыв доступ к живому ключу — ради операции, которая ключом не пользуется.
