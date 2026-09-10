# Active delivery status

- **slug:** hotfix-reaper-kills-live-run
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_collect_run_timeout.py::test_reaper_threshold_must_exceed_run_timeout
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** n/a reason=класс S, дефект найден расчётом и воспроизводится тестом
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель
- **hooks:** claude
- **blockers:** none
- **waivers:** none
- **new_dependency:** none
- **runtime_paths:** none reason=правка касается времени и конфига, не сети
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** конфиг с `COLLECT_RUN_STALE_SEC` ≤ `COLLECT_RUN_TIMEOUT_SEC` не даёт процессу стартовать; прогон, упёршийся в лимит времени, закрывается `partial` с причиной, а не молча продолжает работу
- **observe_until:** 2026-09-24
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Почему поставка вклинилась перед Ф3б

Дефект Z1 из `docs/FINDINGS.md`: реапер добьёт живой прогон. Он не проявляется
на фикстурах и не проявится до Ф7 — а к Ф7 он будет стоить платного прогона,
убитого на середине. Ф3б (её спека уже в git, коммит 9990114) открывается
сразу после.
