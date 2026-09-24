# Active delivery status

- **slug:** domain-as-a-human-reads-it
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_cases_builder.py::test_idn_domain_reads_as_a_human_wrote_it
- **diagnosis:** n/a reason=дефект виден глазами в готовом PDF, воспроизводится одним доменом
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-13 by=human:anthony («протестировать всё в сервисе, даже корректное формирование графиков, выгрузку»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** case-pdf reason=имя файла и заголовок видны только на собранном артефакте
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=чистая функция над строкой
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** в кейсе и в имени файла домен выглядит так, как его пишет человек, а в запросах к Ahrefs — так, как требует API
- **observe_until:** 2026-10-08 (сдвинут 24.09.2026: до выкладки PR #7 прода не было — наблюдать было негде; окно отсчитано от выкладки, +14 дней. Сигнал про живые данные наблюдаем только после перевода в live — это решение владельца; не переведут к сроку — сдвиг с той же причиной)
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Сплошная проверка 13.09.2026: в архиве кейсов лежат файлы
`xn----7sbbfcp9amtfeggde.example — Кейс.pdf`, и тот же punycode стоит в
заголовке PDF, который уходит клиенту агентства.

Приём приводит домен к каноническому хосту — это правильно: в таком виде его
ждёт Ahrefs и по нему сходятся записи в базе. Но **канон для API и имя для
человека — разные вещи**, и кейс показывает первое там, где нужно второе.
