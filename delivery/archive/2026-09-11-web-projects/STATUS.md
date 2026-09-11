# Active delivery status

- **slug:** web-projects
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («бери» — следующая поставка Ф6: таблица проектов с фильтрами)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no reason=TanStack Table стоит с каркаса Ф6
- **runtime_paths:** web/src/pages/ProjectsPage.tsx reason=таблица со ста строками и фильтрами проверяется исполнением: страница обязана открыться на настоящих данных, а не только в jsdom
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** сотрудник находит проект по домену и видит его группу, не спрашивая инженера; «нет данных» отличается от «плохого» на экране, а не только в базе
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Прогон собран, вердикты записаны — и посмотреть на них можно только курлом:
на месте «Проектов» стоит заглушка. Это главный экран просмотра: с него человек
понимает, что вообще получилось из загруженного списка.

Главное требование здесь — **не слить «нет данных» с «плохим»**. В базе это
разные группы с Ф3, и на экране они обязаны выглядеть по-разному: «плохой» —
результат, «данных не хватает» — незаконченная работа.
