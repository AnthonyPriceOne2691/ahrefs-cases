# Active delivery status

- **slug:** case-pdf
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («ставим зависимость», «делай пока сам, сделай в лучших традициях визуала, чтобы было цветным, информативным»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** tests reason=первый артефакт фазы: тест открывает готовый PDF и проверяет сигнатуру, число страниц и отсутствие домена в анонимном кейсе
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** yes reason=jinja2 и weasyprint переходят из опциональных в обязательные: PDF — требование ТЗ, а не режим. Обе в манифесте с Ф1, системные cairo/pango на машине есть; установку выполнил человек
- **runtime_paths:** src/ahrefs_cases/export/pdf_renderer.py reason=вёрстка проверяется только исполнением: одностраничность, разрывы таблицы и кириллица в системных шрифтах видны в готовом PDF, а не в шаблоне
- **model_surface:** n/a reason=текст кейса шаблонный, модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** `render <домен>` кладёт PDF на диск и печатает путь и число страниц; заблокированный стоп-листом кейс печатает правило, а не файл
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Цель фазы Ф4 — «первый готовый PDF». Здесь она закрывается: кейс становится
файлом. Вид свой (референсов от заказчика нет), палитра и правила плиток — из
руководства по визуализации, чтобы цвет метрики в плитке совпал с её цветом на
графиках следующей поставки.

Вместе с первым артефактом появляется обязанность его проверять: стоп-лист по
тексту и по гео стоит **перед** выдачей и работает fail-closed.
