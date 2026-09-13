# Active delivery status

- **slug:** run-tells-what-happened
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** tests/test_api_runs.py::test_run_card_names_every_skipped_domain
- **diagnosis:** n/a reason=не дефект кода: данные пишутся, но наружу не отдаются
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («протестировать всё в сервисе… остальное должно работать безукоризненно»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=чтение уже записанного, без внешних вызовов
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** по каждому прогону видно, сколько доменов пропущено и почему — не в логах контейнера, а на экране
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

ТЗ требует прямо: «логи прогона: сколько обработано, сколько пропущено и
почему». Судьба каждого домена пишется в `run_items` с исходом и причиной — и
**нигде не отдаётся**: в API есть только счётчики `projects_total/ok/failed`,
и даже слова «пропущено» среди них нет.

Пропуск — штатный исход, а не ошибка: домен без данных, молодой домен, нехватка
квоты, остановка предохранителем. Сегодня прогон на сто доменов, где двадцать
пропущено, выглядит на экране как «80 из 100» без единого слова о том, что
случилось с остальными двадцатью и надо ли что-то делать.
