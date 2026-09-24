# Active delivery status

- **slug:** user-can-be-deleted-while-the-journal-stays
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** tests/test_api_users.py::test_user_with_runs_is_not_deleted_but_named
- **diagnosis:** n/a reason=не дефект: недостающая возможность, названная владельцем
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («добавь возможность удалять пользователей, это может делать только админ и инженер»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=удаление проверяется на своих строках, внешних вызовов нет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** учётка без прогонов удаляется, учётка с прогонами — нет, и сказано почему
- **observe_until:** 2026-10-08 (сдвинут 24.09.2026: до выкладки PR #7 прода не было — наблюдать было негде; окно отсчитано от выкладки, +14 дней. Сигнал про живые данные наблюдаем только после перевода в live — это решение владельца; не переведут к сроку — сдвиг с той же причиной)
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Удаления пользователя не было вовсе, и это было решение, а не пропуск: за
учёткой тянется журнал прогонов (`runs.started_by` с `ON DELETE RESTRICT`), и
стереть её значит потерять, кто их запускал.

Владелец попросил удаление и уточнил: прогоны удалять не нужно, история
остаётся, и рядом с именем автора пусть стоит «(удалён)».

Отсюда два пути с одним видимым поведением. За учёткой есть прогоны — строка
остаётся помеченной: из списка человек пропадает, войти не может, а журнал
по-прежнему называет его по имени. Прогонов нет — строка удаляется
по-настоящему, и почта освобождается (учётку с опечаткой иначе пришлось бы
обходить вечно). Право — `manage_users`, то есть админ и инженер по таблице
доступа ТЗ.

Попутно журнал научился показывать автора вовсе: раньше в ответе лежал только
`started_by` числом, и экран не показывал его никак.
