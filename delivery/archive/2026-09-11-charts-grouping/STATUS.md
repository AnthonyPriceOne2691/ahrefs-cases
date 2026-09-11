# Active delivery status

- **slug:** charts-grouping
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («давай» — следующая поставка Ф6: тумблер «месяц/квартал/год»)
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** SVG — артефакт: тест сверяет свёрнутые числа с ручным расчётом по правилу потока и запаса
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=поведение закрыто тестами; рисунок проверен глазами на живом стеке
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** на длинном проекте кривая читается: помесячная пила сворачивается в кварталы, и рост виден без объяснений
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Решение владельца от 11.09.2026: тумблер «месяц/квартал/год» — **бесплатная
агрегация**, потому что данные уже собраны помесячно. На двухлетнем проекте
помесячная кривая — это 24 точки пилы, по которой рост видно хуже, чем по
восьми кварталам.

Свёртка при этом не косметика: **правило зависит от природы метрики**. Трафик
за квартал — сумма трёх месяцев; ссылающиеся домены за квартал — значение на
конец. Сложить домены за три месяца значило бы показать втрое больше доменов,
чем есть, — и в PDF такое заметят не сразу.
