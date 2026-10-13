# Verify report: brief-known-more

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M137–M141 (repro) | прежнее правило из `main` на тех же входах | **до правки:** у «seo-инструменты», «DIY-ритейл», «ПО», «софт для разработчиков», «контент» типа сайта нет; «ПО» и «финтех» — тематика нишей «(ниша из файла)»; «Кто подготовил», «Трудности», «Особенности» не подставляются; после — зелёные |
| M142 (repro) | `card-brief.test.tsx` на прежнем `Brief.tsx` | **до правки** — 2 красных (строка «пунктов для специалиста», кнопки нет); после — зелёные |
| M137–M141 | `tests/test_brief_known.py` — правило подстановки по фактам | 62 passed: «вёл проект» и запись специалиста; просадка 07.2026 −18 %, DR 32 → 29, обе, ниже порогов, месяц до старта, пропуск месяца, нет ряда; три самые глубокие из пяти по порядку месяцев; пары домена; YMYL по словарю и по тематике специалиста, «Другое», записанные «Особенности»; ниши прода и узость слов («музыкальные инструменты», «товары по уходу», «ПО-шник на час») |
| M139, M143 | `tests/test_api_project_brief.py` — карточка на дев-базе | 13 passed: линкбилдинг внахлёст — в «Параллельно», та же услуга («SEO ») и период без пересечения — нет; сличающий тест на проекте с просадкой 04.2025 −25 %, DR 32 → 29, парой домена, YMYL и «вёл проект» — карточка и лист печатают одно по всем пунктам (L258) |
| M142 | vitest `card-brief.test.tsx` | 13 passed: «сервис подставил 2 пункта из 6, специалисту осталось 4», «Показать / Скрыть подставленное»; «1 пункт» |
| Полный сьют | `pytest` (дев-база) | 979 passed, 12 skipped (8 мин 10 с) |
| Фронт | `vitest`, `tsc --noEmit`, ESLint, Prettier | 259 passed; чисто |

## Исполнение рисковых путей

- `src/ahrefs_cases/export/brief_sheet.py`, `src/ahrefs_cases/cases/builder.py` — стенд (база `cases_geo`, провайдер fixture, API и
  воркер перезапущены на коде ветки): «Пересобрать кейсы» №2370 — 66 собрано из 80; у всех 67 кейсов библиотеки «Кто
  подготовил» — «вёл проект»; у zooplus.de — «Линкбилдинг, 06.2025 — 05.2026 (тот же домен в базе)»; YMYL — у 11 (финансы,
  финтех, медицина); подстановок на кейс 6–10, в среднем 8,8. at=2026-10-13
- «Трудности» на стенде: синтетические ряды растут ровно (худшая просадка −1,5 %, DR растёт у всех) — подсказке не о
  чем сказать. Для проверки трафик zooplus.de за 02.2025 временно умножен на 0,75 через сессию приложения (значение
  записано): пересборка №2371 — «Просадка органического трафика в 02.2025: -19 % к 01.2025 (по динамике Ahrefs —
  уточните причину)», `zooplus.de — Кейс v17.pdf` растеризован — длинное значение переносится внутри ячейки, бриф — 2
  страницы, «Динамика» — 1; значение возвращено (67 396), пересборка №2372 — подсказок снова нет. at=2026-10-13
- Карточка в Chrome (стенд, zooplus.de, бриф пуст): «Бриф ещё не заполнен: сервис подставил 10 пунктов из 22,
  специалисту осталось 12» и «Показать подставленное» — десять пунктов с источником; после «Скрыть» верх «Почему эта
  группа» тот же — 1134 px. at=2026-10-13

## Что нашла проверка

- **Данные стенда не дают ни одной просадки** — без временной правки подсказку «Трудности» в PDF не увидеть; на проде у
  jupid.com DR 32 → 29 — подсказка появится после пересборки.
- **Ожидание в моём тесте было неверным:** сличающий тест M136 сначала сохраняет бриф, а сохранение подписывает «Кто
  подготовил» (инв. 10а) — подстановки там нет; ожидание возвращено.
- **Дайджест привязал утверждения M143 к L258 и M137** — пометка урока в докстроке и комментарий «# M137» перетягивали
  следующие строки; пометки переставлены, каждое утверждение — к своему примеру.

## Ревью рисковых мест

**Данные.** Миграций нет. Подстановка не пишется в бриф — считается при сборке и чтении. Новый запрос — проекты того
же домена (`cases/parallel.py`): идёт по индексу ограничения `uq_project_domain_period` (домен — первая колонка),
порядок — по началу периода и id (L218).

**Деньги.** Units не тратятся: всё — по купленным и записанным данным; «Пересобрать кейсы» бесплатна.

**Безопасность.** Новых путей и прав нет. Карточка теперь называет услуги и периоды других проектов того же домена —
их и так видит любой, кто читает проекты.

**Интеграция.** `brief_known` — то же поле, больше ключей; `BriefFacts` шире — оба вызывающих называют каждое поле
(L74). Экран: строка пустого брифа считает по `brief_known`, не по каталогу (L260).

## Чего проверка НЕ доказывает

- Прод: «Трудности» на настоящих рядах (на стенде — только синтетическая просадка), YMYL и «вёл проект» в PDF — после
  выкатки и «Пересобрать кейсы».
- Пороги 15 % и 3 пункта — умолчания агента; правила команды нет.

## Verdict
- [x] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **28**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M139	assert "parallel_services" not in _card(client, project_id)["brief_known"]
M139	assert known["parallel_services"] == "Линкбилдинг, 06.2025 — 05.2026 (тот же домен в базе)"
M143	assert project is not None
M143	assert project is not None
M143	assert printed == known
M138	assert known["difficulties"] == (  # M138
M139	assert known["parallel_services"] == parallel
M140	assert known["features"] == (  # M140
M137	assert known["prepared_by"] == "i.p (вёл проект, из файла)"  # M137
M137	assert _known(brief, owner=owner).get("prepared_by") == prepared_by
M138	assert (DROP_SHARE, RATING_DROP) == (0.15, 3.0)
M138	assert _known(traffic=traffic, rating=rating).get("difficulties") == difficulties
M138	assert MAX_DROPS == 3
M138	assert found == (
M139	assert _known(parallel=(linkbuilding,))["parallel_services"] == (
M139	assert _known(parallel=(linkbuilding, own_word))["parallel_services"] == (
M139	assert "parallel_services" not in _known()
M140	assert _known(brief, niche=niche).get("features") == features
M141	assert known["topic"] == f"{topic} (по нише «{niche}»)"
M141	assert known["site_type"] == f"{site_type} (по нише «{niche}»)"
M141	assert not _known(niche=niche).get(field, "").startswith(not_this)
M142	expect(
M142	expect(screen.queryByText('Путешествия')).not.toBeInTheDocument();
M142	expect(screen.getByText('Путешествия')).toBeInTheDocument();
M142	expect(screen.getByText('120 (объём работ из файла)')).toBeInTheDocument();
M142	expect(screen.queryByText('заполняет специалист')).not.toBeInTheDocument();
M142	expect(screen.queryByText('Путешествия')).not.toBeInTheDocument();
M142	expect(
```

✅ **Каждое утверждение ведёт к примеру спеки** (M137 M138 M139 M140 M141 M142 M143), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 13 code (+18 process docs) / +658/-58 (net +600) |
| commits | 3 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | no — новые примеры в прежних оракулах (`test_brief_known.py`, `test_api_project_brief.py`, `card-brief.test.tsx`) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
