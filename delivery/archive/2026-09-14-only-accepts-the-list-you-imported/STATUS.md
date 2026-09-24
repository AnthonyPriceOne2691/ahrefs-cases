# Active delivery status

- **slug:** only-accepts-the-list-you-imported
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** tests/test_cli_exit_codes.py::test_only_reads_the_domain_column_of_the_intake_file
- **diagnosis:** n/a reason=найдено исполнением: тот же файл, которым делали intake, `--only` не принимает
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 14.09.2026)
- **human_ok_spec:** yes at=2026-09-14 by=human:anthony («я сам хочу погонять с импортом из файла»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=разбор аргумента, внешних вызовов нет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** прогон по списку из файла приёма стартует, а не отказывает на строке заголовков
- **observe_until:** 2026-10-08 (сдвинут 24.09.2026: до выкладки PR #7 прода не было — наблюдать было негде; окно отсчитано от выкладки, +14 дней. Сигнал про живые данные наблюдаем только после перевода в live — это решение владельца; не переведут к сроку — сдвиг с той же причиной)
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Оператор загружает список файлом — это и есть боевой сценарий. Тот же файл он
естественно подставит в `--only`, чтобы прогон шёл ровно по нему. Сейчас это
отвечает:

```
--only: domain,period_start,period_end,... : не домен (invalid_domain)
```

Сообщение честное и бесполезное: человек видит свою строку заголовков и не
понимает, чего от него хотят. `--only` ждёт файл с доменами построчно, и нигде,
кроме докстроки, об этом не сказано.

Найдено исполнением 14.09.2026 при сборке боевого набора: первая же команда
после `intake` отказала.
