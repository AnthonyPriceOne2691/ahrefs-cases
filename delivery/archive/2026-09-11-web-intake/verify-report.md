# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (утверждения ведут к примерам спеки E1–E13)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34602699908
**Commit:** bab5523

## Shape oracles
- [x] PASS — pre-commit, 29 хуков, упавших 0
- [x] PASS — предохранители: net_loc 787 при пороге 800, файлов 13 из 25
- [x] PASS — `tsc --noEmit` чист, ESLint без роста предупреждений (0 новых)

## Behavior oracles
- [x] PASS — vitest 23 теста, 4 файла; pytest 401 passed, 1 skipped
- [x] PASS — примеры E1–E12 закрыты тестами; E13 (узкий экран) — глазами

## Product oracles
- [x] PASS — список загружается файлом и ссылкой, отчёт называет числа и строки
- [x] PASS — смета видна до запуска: units, запросы, остаток квоты, разбивка
- [x] PASS — при нехватке квоты кнопка недоступна, причина названа словами
- [x] PASS — запущенный прогон виден номером и состоянием, `409` — номером активного

## Ревью рисковых мест

**Блокировка до траты, а не после.** Главное свойство экрана проверяется
исполнением, а не разметкой: `start-run` обязана быть `disabled`, когда смета
говорит «нельзя». Два теста, потому что причин две и они разные — «не хватает
units» лечится лимитом или ожиданием, «остаток неизвестен» — доступом к Ahrefs.

**Кнопка недоступна, а не спрятана.** Пропавшая кнопка не объясняет, почему её
нет: человек идёт искать поломку вместо того, чтобы поднять лимит. Причина
стоит рядом текстом сервера.

**Смета пересчитывается после приёма.** Иначе экран показывал бы цену
предыдущего списка, и решение о запуске принималось бы по ней. Закрыто E13:
первый ответ сметы — нулевой список, после приёма виден новый.

**Скрытый раздел — не защита, и это по-прежнему так.** «Загрузка» стоит под
правом `run`, но приём и запуск закрыты правом на сервере, и серверные тесты
предыдущей поставки это держат.

**Текст отказа — серверный.** Формат файла, доступ к таблице, номер активного
прогона: собственная формулировка на фронте разошлась бы с серверной и
оставила бы человека без следующего шага.

**Безопасность.** Экран поднимает три её стороны, и ни одна не нова: токен
уходит в заголовке тем же клиентом, что и раньше; раздел закрыт правом `run`
только в меню, а приём и запуск проверяет сервер; имя файла уходит параметром
запроса и экранируется (`encodeURIComponent`), путей из него никто не строит.
Тело файла браузер размечает сам — свой `Content-Type` мы не подставляем, чтобы
не соврать серверу о содержимом.

**Деньги.** Экран сам ничего не покупает: смета бесплатна, прогон запускается
одной кнопкой под замком на второй (серверный, из Ф5).

**Что всплыло по дороге.** Появление настоящего экрана на первом месте в меню
уронило чужой тест входа: `renderApp` давал только Mantine, а экран ходит в
API и требует клиента запросов. Провайдеры в тестовом рендере теперь те же,
что в `main.tsx`, — иначе «добавил экран» ломает тест, который его не знает.

## Что осталось за границей

Журнал прогонов, проекты, карточка, кейсы, расход, пороги и люди — следующие
поставки Ф6. Здесь виден только тот прогон, который запустили с этого экрана.
## Assertion digest (ревью ожиданий, не кода)

База: `HEAD~1` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **21**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
E1	expect(labels(['read', 'run'])[0]).toBe('Загрузка');
E1	expect(labels(['read'])).not.toContain('Загрузка');
E3	expect(await screen.findByText('принято 10')).toBeInTheDocument();
E3	expect(screen.getByText('создано 10')).toBeInTheDocument();
E3	expect(screen.getByText('обновлено 0')).toBeInTheDocument();
E4	expect(await screen.findByText('12')).toBeInTheDocument();
E4	expect(screen.getByText('дата не разобрана')).toBeInTheDocument();
E5	expect(await screen.findByText(/не понимаю формат файла/)).toBeInTheDocument();
E6	expect(await screen.findByText(/таблица недоступна по ссылке/)).toBeInTheDocument();
E8	expect(await screen.findByText('units по смете 1980')).toBeInTheDocument();
E8	expect(screen.getByText(/Остаток квоты: 9\s?500/)).toBeInTheDocument();
E8	expect(screen.getByText(/organic-traffic-history/)).toBeInTheDocument();
E9	expect(await screen.findByText(/не хватает units: остаток 300/)).toBeInTheDocument();
E9	expect(screen.getByTestId('start-run')).toBeDisabled();
E10	expect(await screen.findByText(/остаток квоты Ahrefs неизвестен/)).toBeInTheDocument();
E10	expect(screen.getByText('Остаток квоты: неизвестен')).toBeInTheDocument();
E10	expect(screen.getByTestId('start-run')).toBeDisabled();
E11	expect(await screen.findByText(/Прогон №7/)).toBeInTheDocument();
E12	expect(await screen.findByText(/прогон 4 уже идёт/)).toBeInTheDocument();
E13	expect(await screen.findByText('units по смете 0')).toBeInTheDocument();
E13	await waitFor(() => expect(screen.getByText('units по смете 1980')).toBeInTheDocument());
```

✅ **Каждое утверждение ведёт к примеру спеки** (E1 E10 E11 E12 E13 E3 E4 E5 E6 E8 E9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Spec coverage gaps
- **Журнал прогонов** экраном не делался — следующая поставка; здесь виден
  только прогон, запущенный отсюда.
- **Перетаскивание файла мышью** не делалось: у drop-zone свои состояния и свои
  тесты, а сценарий закрывает кнопка выбора.
- **Догрузка (`refresh`) и ступени 2–3** не запускаются с экрана: они стоят
  денег избирательно, и их место на экране прогонов.

## Verdict
- [x] READY FOR HANDOFF

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base HEAD~1 -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 13 code (+8 process docs) / +798/-11 (net +787) |
| commits | 1 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — web/src/pages/__tests__/intake.test.tsx (новый оракул) |
| implement_retries | 2 — чужой тест входа упал на новом экране (провайдеры в тестовом рендере), и `accept` у выбора файла не пускал `.pdf` |
| verify_fails_before_green | 0 (CI зелёный с первого прогона) |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
