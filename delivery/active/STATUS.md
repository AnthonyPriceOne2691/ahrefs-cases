# Active delivery status

- **slug:** f2a-intake-fixtures
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes (by=human:anthony, at=2026-09-10) — спека с примерами B1–B12 и границей Ф2а/Ф2б подписана
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=поставка не производит файловых артефактов; PDF и ZIP появятся в Ф4
- **ci-oracles:** tooling
  <!-- Без изменений с Ф1: гейт мержа (`scripts/merge_guard.sh` + pre-push hook +
       `needs:`) и ruleset `main` id 22794937. Required status checks выключены
       осознанно — см. решение в архиве `2026-09-10-f1-skeleton/decisions.md`. -->
- **worktree:** none reason=единственный исполнитель, работа прямыми коммитами в main; пересматривается вместе с ci-oracles при появлении второго человека
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
  <!-- Пример входного файла от заказчика не пришёл (см. «Подготовить до старта»),
       но приём разрабатывается против собственного `config/projects.example.csv`
       по десяти полям §4 — материал заказчика проверит форму, а не заменит её. -->
- **waivers:** none
- **new_dependency:** openpyxl reason=чтение XLSX в intake; в манифест попал авансом в Ф1, в оборот вводится здесь by=agent:claude
- **new_dependency:** chardet reason=определение кодировки CSV (выгрузка из Excel приходит в cp1251) by=agent:claude
- **runtime_paths:** network:docs.google.com reason=CSV-экспорт опубликованной Google Sheet — единственный сетевой путь поставки; в тестах заглушен, fixture-провайдер наружу не ходит
- **model_surface:** n/a reason=в MVP текст кейса шаблонный, модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** <заполняется на handoff>
- **observe_until:** <заполняется на handoff>
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Граница с Ф2б

Экономия units (кэш закрытых месяцев, инкрементальный `date_from`, single-flight,
смета, preflight квоты, воронка) вынесена в следующую поставку намеренно: главный
DoD Ф2 — «повторный прогон не делает повторных запросов». Если бы кэш и тест на
него писались в одной поставке с самим сбором, проверка экономии стояла бы на
коде, написанном под неё же. Здесь сбор запрашивает всё честно и дорого; Ф2б
делает его дешёвым и предъявляет разницу числом.
