# Active delivery status

- **slug:** f3v-diagnose
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай полностью добьём Ф3» — состав фазы объявлен в docs/PHASES_V3.md: диагностика «плохих» и выключаемый блок нормализации)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=файловых артефактов нет; PDF и ZIP — Ф4
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=диагностика считает по уже собранным сериям
- **runtime_paths:** none reason=диагностика не ходит в сеть и не пишет в базу; проверяется падающим httpx
- **model_surface:** n/a reason=текст диагностики шаблонный, модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `diagnose` печатает по каждому «плохому» пик, глубину падения и месяц начала либо один из двух других диагнозов; отсутствие данных шага 2 названо словами с ценой вопроса; версия порогов с ненулевым `normalize_after_months` отвергается на разборе — и классификацией, и пересчётом, и предпросмотром
- **observe_until:** 2026-09-25
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Чем закрывается Ф3

Последний пункт состава фазы из `docs/PHASES_V3.md` — диагностика «плохих».
Вместе с ним закрывается долг, который фаза оставила осознанно: блок
нормализации на длительность работ разбирается из порогов, но **не применяется**
и об этом молчит. Формулы у нас по-прежнему нет — значит блок обязан не молчать.

После приёмки идёт волна В2 (③ OKF): по `docs/CONTOUR_ROLLOUT.md` её предельный
срок — начало Ф8, и причина названа там же: при калибровке правка порога будет
ломать golden-таблицы, и снимок захочется перезаписать вместо того, чтобы
удовлетворить.
