# Verify report: project-card-hands-over-the-case

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| Карточка целиком | `vitest run src/pages/__tests__/card.test.tsx` | 20 passed |
| Смена шага падала до правки | те же тесты на исходниках HEAD | 3 failed из 3 новых |
| Фильтр и выборка | `pytest tests/test_api_read.py -k "selection or library"` | 6 passed |
| Бэкенд целиком | `pytest -q` | 580 passed, 1 skipped |
| Фронт целиком | `vitest run` | 140 passed |
| Типы и стиль | `tsc --noEmit`, `eslint src` | чисто; 0 предупреждений при планке 0 |

## Что пришлось разобрать по дороге

Ратчет предупреждений ESLint (планка 0) поймал рост до 5. Все пять — мои, и все
одного рода: функции переросли восемьдесят строк. Разобрано на части, а не
заглушено: `card/Dynamics.tsx` (блок «Динамика»), `cases/SelectionBar.tsx`,
`cases/selection.ts` (отметки и скачивание выборки), `LibraryState` и
`Publishing` внутри своих файлов. Заодно ушли три `non-null assertion`: в
`CasePdf` вместо `row!` считается `ready` — кейс, который действительно можно
скачать, и обработчику не приходится верить кнопке на слово.

## Чего проверка НЕ доказывает

Прокрутка. Тесты держат **причину** — блок и переключатель не снимаются, — а
саму прокрутку jsdom не воспроизводит: высоты у него нулевые. Что страницу
больше не бросает наверх, проверяется глазами на стенде; это и записано в
`observe_signal`.
## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **6**, из них без ссылки на пример спеки:
**6**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
-	expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument();
-	expect(await screen.findByText('Сессия истекла, войдите заново')).toBeInTheDocument();
-	expect(screen.queryByText('нужен действующий токен')).not.toBeInTheDocument();
-	await waitFor(() => expect(storedToken()).toBeNull());
-	await expect(
-	expect(screen.queryByText('Сессия истекла, войдите заново')).not.toBeInTheDocument();
```

⚠ **Ни одно утверждение не ссылается на пример из спеки.** Значит все
ожидания придумал исполнитель — это ровно тот круг, о котором §3.1d.

Читать нужно **только строки с `-` в первой колонке**: их ожидание
ничем не подписано. Подпись: `asserts_reviewed_by: human:… at=…`.

asserts_without_example: 6

asserts_reviewed_by: human:anthony at=2026-09-15
