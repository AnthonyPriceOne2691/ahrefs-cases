# Active delivery status

- **slug:** api-charts
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** tests/test_api_charts.py::test_card_reads_series_of_the_configured_source
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** specify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («а потом Дальше по Ф6» — план Ф6 ①: карточка проекта с графиками, SVG рисует бэкенд)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** SVG — артефакт: тест проверяет, что ответ рисуется и что он тот же, что уходит в PDF
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=поведение закрыто тестами; живого прогона поставка не требует
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** график в вебе и график в PDF одного проекта совпадают до символа; в живом режиме карточка не пустеет
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Карточка проекта во фронте — следующий экран Ф6, и рисовать графики ей нечем:
`GET /api/projects/{id}/charts` не существует. Решение владельца от 11.09.2026
прямое: **один SVG на бэкенде идёт и в PDF, и в веб-карточку** — второй рисунок
разошёлся бы с первым, и клиент увидел бы одно, а сотрудник другое.

Попутно чинится повторение урока **L53**, найденное при осмотре: карточка берёт
источник рядов умолчанием обработчика (`source = MetricSource.FIXTURE`). В живом
режиме ряды записаны как `live`, и карточка показала бы пустые графики при
целой базе — то есть сломалась бы ровно в Ф7, на боевом ключе.
