# Active delivery status

- **slug:** live-run-tails
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** bugfix
- **repro_test:** tests/test_collect_quota.py::test_ceiling_is_the_smaller_of_two_limits
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-12 by=human:anthony («три хвоста» — по итогам живого прогона Ф7)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** case-pdf reason=обрезанная подпись видна только на готовом PDF, проверяется рендером
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** src/ahrefs_cases/export/charts.py reason=обрезание подписи ловится только глазами на собранном PDF, в разметке его не видно
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** прогон собирает названный список, а не всю базу; остаток квоты не обещает больше, чем даст воркспейс; подпись значения на кривой видна целиком
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Три хвоста живого прогона 12.09.2026, каждый нашёлся исполнением:

1. **Остаток квоты считается только по ключу.** Настоящий потолок — минимум с
   воркспейсом: он общий с другими сервисами агентства, и если его выжгут,
   preflight скажет «хватает», а запросы начнут отбиваться на середине прогона.
2. **Живой `collect` идёт по всей базе.** На стенде он ушёл в Ahrefs за
   фикстурными доменами — часть из них оказалась настоящими сайтами.
3. **Подпись последнего значения на кривой обрезана** границей `viewBox`
   («3 596 46…»). Артефакт уходит клиенту.
