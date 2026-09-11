# Active delivery status

- **slug:** thresholds-in-words
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («пороги» — следующий экран по согласованному порядку Ф6)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/ThresholdsPage.tsx reason=предпросмотр считает по всей базе, и что он покажет на настоящих данных, видно только исполнением
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** человек видит действующие пороги словами, а не JSON'ом: цифру утверждают, понимая, что она включает
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

`/thresholds` — заглушка, хотя API отдаёт версии, предпросмотр, активацию и
пересчёт. Пороги — самое опасное место сервиса: одна цифра перекладывает по
группам всю базу и меняет, какие кейсы уйдут клиентам.

Эта поставка закрывает первый вопрос: **что действует сейчас** — условия групп,
пригодность и ограничители человеческим языком. Список версий с предпросмотром
последствий и правка приедут следующими поставками.

## Почему поставка разрезана дважды

Сначала от просмотра отделили редактор: у формы правки два десятка полей, а
граница совпадает с правами в API (`read` против `edit_thresholds`).

Потом прогон показал, что и просмотр — две работы: «что действует» и «что
изменится». Вместе они дали 934 строки при пороге 800, и разрез прошёл по
вопросам, а не по случайному месту (L50, L91). В этой поставке — первая
половина: действующие пороги словами.
