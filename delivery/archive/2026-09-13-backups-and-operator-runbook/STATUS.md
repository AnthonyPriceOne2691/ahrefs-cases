# Active delivery status

- **slug:** backups-and-operator-runbook
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** tests/test_backup_covers_state.py
- **diagnosis:** n/a reason=не дефект: подготовка Ф9 в части, которой не нужен сервер
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («плюс подготовка Ф9 без сервера» — выбрано в списке работ до калибровки)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефакт бэкапа проверяется восстановлением на сервере, а не в сборке
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** scripts/backup.sh, scripts/restore.sh reason=скрипты работают против настоящего компоуза; проверка — восстановление на сервере, и её делает человек
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** всё состояние, которое нельзя пересобрать, попадает в бэкап; новый том без бэкапа роняет оракул
- **observe_until:** 2026-09-27
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Ф9 ждёт сервера, списка сотрудников и референсных кейсов — но две её части не
ждут ничего: **бэкапы** и **инструкция оператора**. Обе нужны до первого
боевого прогона, а не после: восстанавливать придётся то, за что заплачены
units, а запускать сервис будут шесть-семь человек из четырёх отделов, и
объяснять им сервис голосом — значит объяснять его каждый раз заново.

Мониторинг из Ф9 уже есть: `/api/alerts` считает остаток units, упавшие
прогоны и готовую пачку, экран расхода их показывает. Доставка в Telegram или
Asana ждёт решения заказчика о канале и в поставку не входит.
