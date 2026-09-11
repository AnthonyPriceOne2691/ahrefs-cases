# Active delivery status

- **slug:** web-shell
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай Ф6, управление пользователями, правами и кредами будет на отдельной странице, и видит её только роль — админ»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** yes reason=@testing-library/react, jest-dom, user-event, jsdom — только dev: DoD Ф6 требует vitest на формы и таблицы, а без Testing Library проверять нечем. Установку выполнил человек
- **runtime_paths:** web/src/auth/AuthProvider.tsx reason=выход по 401 проверяется исполнением: протухший токен обязан приводить к форме входа, а не к пустой таблице
- **model_surface:** n/a reason=модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** после входа интерфейс показывает почту и группу в шапке, а меню — только разрешённые разделы; отказ сервера называет недостающее право, а не «что-то пошло не так»
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Сервисом начинают пользоваться люди, а не curl. Меню строится по правам: пункт
виден, если у человека есть право, которое раздел требует.

Скрытая кнопка при этом **не защита** — серверные проверки стоят и остаются.
Это записано в спеке отдельной строкой, чтобы на следующем экране никто не
«сэкономил» на проверке, увидев, что кнопки и так не видно.
