# Active delivery status

- **slug:** f3b-preview
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony (примеры E2, E3, E8 — из спеки Ф3б, подписанной до кода; состав второй половины объявлен при дроблении и принят)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=предпросмотр на существующих таблицах и расчёте Ф3б-1
- **runtime_paths:** none reason=предпросмотр не ходит в сеть и не пишет в базу; проверяется падающим httpx и счётом строк до/после
- **model_surface:** n/a reason=текст кейса шаблонный; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Вторая половина Ф3б

Первая (пересчёт) в архиве: `2026-09-11-f3b-recalc`. Расчёт там уже отделён от
записи (`verdicts.compute_verdict`), чтобы предпросмотр встал на него, а не
завёл второй похожий. Это требование спеки Ф3б, и здесь оно проверяется
примером E3: предпросмотр версии, по которой уже считали, обязан дать тот же
ответ, что даст пересчёт.
