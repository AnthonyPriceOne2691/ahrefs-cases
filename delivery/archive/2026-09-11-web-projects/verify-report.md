# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (дайджест ниже, непривязанных 0)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34612711224
**Commit:** см. `git log -1`

## Shape oracles
- [x] PASS — pre-commit, 29 хуков, упавших 0
- [x] PASS — предохранители: net_loc 604 при пороге 800, файлов 12 из 25
- [x] PASS — `tsc --noEmit` чист, ESLint без роста предупреждений

## Behavior oracles
- [x] PASS — vitest 33 теста (было 24); pytest 414 passed, 1 skipped
- [x] PASS — E1–E10 закрыты тестами

## Product oracles (живой прогон, не только jsdom)
- [x] PASS — экран открыт в поднятом стеке на настоящих данных
- [x] PASS — после `collect` → `stage2` → `classify` на фикстурах таблица
      показала 6 «хороший» и 4 «данных не хватает» своими цветами
- [x] PASS — до классификации те же строки честно подписаны «не
      классифицирован», а не пустой ячейкой

## Ревью рисковых мест

**«Нет данных» не слито с «плохим».** В базе это разные группы с Ф3, и на
экране они разные словом и цветом: у «плохого» результат есть и он слабый
(кейса не будет), у «нет данных» работа не закончена (докупить историю и
пересчитать). Проверяется не подписью, а атрибутом `data-group` — подпись
могла бы совпасть с чипом фильтра, и тест поймал бы не то (так и случилось на
первом прогоне).

**Фильтры уходят на сервер.** Сервер отдаёт страницу, и фильтрация видимых
строк соврала бы «хороших нет», когда они на второй. Проверяется по адресу
запроса, а не по содержимому таблицы.

**Смена фильтра возвращает на первую страницу.** Иначе человек, отфильтровав на
третьей, увидит пустоту и решит, что подходящих проектов нет.

**Полная страница не значит «есть ещё».** Кнопка «Вперёд» доступна, пока строк
ровно страница; это честное «возможно, есть ещё», и человек видит номер
страницы, а не бесконечную ленту, скрывающую потолок выдачи.

**Цвет из общего словаря.** Группы красятся из `theme.groupInk` — того же
источника, что плитки и графики. Второй словарь разошёлся бы с первым при
первой правке.

**Выпадающий список заменён чипами.** Причина продуктовая: пять
взаимоисключающих значений видны сразу, это один клик вместо двух и никакого
попапа на узком экране. Побочно вскрылось, что попап Mantine в jsdom рендерится
секундами: файл тестов шёл 140 секунд и падал по таймауту, после замены — 1
секунда. Тест, который не успевает, ничего не проверяет.

**Безопасность.** Экран за правом `read`, как и раздел; серверная проверка
стоит и остаётся. Ни одного адреса бэкенда в коде — ходим через прокси.

**Деньги.** Экран только читает; ни один его запрос ничего не покупает.

**Транзакция БД.** Фронт в базу не ходит.

## Что осталось за границей

Карточка проекта — следующая поставка (`web-project-card`): строка таблицы уже
ведёт на `/projects/:id`, где пока честная заглушка. Сортировка на сервере и
выгрузка таблицы в файл не делались — ТЗ их не просит.
## Assertion digest (ревью ожиданий, не кода)

База: `HEAD~1` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **17**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
E1	expect(await screen.findByText('good.example')).toBeInTheDocument();
E1	expect(screen.getByText('хороший')).toBeInTheDocument();
E1	expect(screen.getByText('плохой')).toBeInTheDocument();
E1	expect(screen.getByText('не классифицирован')).toBeInTheDocument();
E1	expect(screen.getByText('1 400')).toBeInTheDocument();
E3	expect(groups).toContain('insufficient_data');
E3	expect(groups).toContain('poor');
E3	expect(screen.getByText('плохой')).toBeInTheDocument();
E10	await waitFor(() => expect(window.location.pathname).toBe('/projects/1'));
E4	await waitFor(() => expect(urls.some((url) => url.includes('group=good'))).toBe(true));
E5	await waitFor(() => expect(urls.some((url) => url.includes('query=good'))).toBe(true));
E9	expect(screen.getByRole('button', { name: 'Назад' })).toBeDisabled();
E9	expect(await screen.findByText('Страница 2')).toBeInTheDocument();
E9	await waitFor(() => expect(urls.some((url) => url.includes('offset=50'))).toBe(true));
E7	expect(await screen.findByText(/Загрузите список/)).toBeInTheDocument();
E6	expect(await screen.findByText(/Снимите фильтр/)).toBeInTheDocument();
E8	expect(await screen.findByText(/нет права read/)).toBeInTheDocument();
```

✅ **Каждое утверждение ведёт к примеру спеки** (E1 E10 E3 E4 E5 E6 E7 E8 E9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Spec coverage gaps
- **Сортировка** не выводилась наружу: API отдаёт по домену, второй порядок
  потребовал бы своего параметра и своей проверки границ.
- **Массовые действия** над выбранными проектами не делались: их нет в ТЗ.

## Verdict
- [x] READY FOR HANDOFF

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base HEAD~1 -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 12 code (+8 process docs) / +604/-0 (net +604) |
| commits | 1 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — web/src/pages/__tests__/projects.test.tsx (новый оракул) |
| implement_retries | 3 — роутер в тестовом рендере, попап Mantine (140 с и таймауты), подпись чипа, пойманная вместо бейджа |
| verify_fails_before_green | 0 |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
