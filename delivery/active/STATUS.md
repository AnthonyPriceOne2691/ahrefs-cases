# Active delivery status

- **slug:** case-charts
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («вот я бы А выбрал, он точнее и лучше показывает динамику» — выбор из двух собранных прототипов)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** tests reason=кривые проверяются на готовом PDF: одна страница, оба графика на месте; геометрия — тестами на путь SVG
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=SVG собирается строками, библиотека рисования не нужна
- **runtime_paths:** src/ahrefs_cases/export/charts.py reason=геометрия проверяется только исполнением: расползание кириллицы и молча погашенный градиент видны в готовом PDF, а не в строке SVG
- **model_surface:** n/a reason=текст кейса шаблонный, модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `render <домен>` кладёт лист с двумя кривыми; в логе видно число точек каждой кривой — если ступень кейса не отработала, кривая позиций будет из двух точек, и это заметно сразу
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Кейс получает две кривые, которых требует ТЗ. Вид выбран владельцем из двух
собранных прототипов: данные плоские, объём даёт оформление — изометрия
выглядела дороже, но её верхняя грань прибавляла каждому столбцу около 1 000
визитов на шкале примера, а форму роста по столбцам труднее прочитать.

Попутно закрывается расхождение, которое иначе заметил бы клиент: последний
месяц кривой не равен точке Б, потому что Б — среднее по окну. Окна А и Б
показаны на кривой, а не спрятаны.
