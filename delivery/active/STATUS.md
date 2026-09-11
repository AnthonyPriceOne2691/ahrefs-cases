# Active delivery status

- **slug:** case-structure
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** verify
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («PDF раньше: данные → текст+PDF-скелет → графики → ZIP»)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов нет: PDF и ZIP собираются поставками 3 и 4 этой же фазы
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** none reason=сборка идёт по уже собранным данным, новых библиотек не требует
- **runtime_paths:** none reason=чистая сборка структуры по прочитанным данным; проверяется тестами без прогона
- **model_surface:** n/a reason=текст кейса шаблонный, модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** команда `cases` печатает по четырём исходам, а не «собрано N»: видно, сколько проектов получило кейс, сколько не положено по группе, у скольких не хватило данных и у скольких вердикта нет вовсе
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Первая из четырёх поставок Ф4. Ф4 целиком в порог 800 строк не влезает, поэтому
режется так: **структура кейса** (эта), **текст со сверкой чисел, стоп-лист и
скелет PDF**, **SVG-графики**, **нейминг и ZIP**. Порядок выбран так, чтобы
готовый PDF можно было открыть глазами на второй поставке, а не на последней:
референтных кейсов от заказчика нет, и вид согласуется по нашему.

Здесь кейс появляется как данные. Главное решение — числа А → Б берутся из
записанного вердикта, а не считаются заново: кейс уходит клиенту рядом с
таблицей, и две формулы одного и того же разойдутся на первом же пересчёте
порогов.

## Состояние осей контура

Волна В3 (⑤ оракулы поведения модели) не пришла: `model_surface: n/a` — в MVP
текст кейса шаблонный, вызова модели не будет. Ось встанет в очередь, если
появится LLM-ветка абзаца (рамки — `docs/AI_USAGE.md`).
