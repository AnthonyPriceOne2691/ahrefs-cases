# Verify report: project-deletion-ui

**Date:** 2026-09-24
**Verifier:** human:anthony (приёмка); оракулы и проход кнопкой — agent:claude
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36047944497
**Commit:** 17117fc

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| K1–K6, K8 до правки | vitest на коммите f8179ae (тесты есть, кода нет) | 6 failed: кнопки «Удалить проект» нет (K2–K5), право подписано ключом (K6), пачка с кейсом удалённого проекта предлагается к скачиванию (K8); K1 — страж, зелёный и до правки |
| K7 до правки | vitest на a172d3d поверх раскрытия из #21 | failed: пометки «(проект удалён)» нет |
| После правки | `vitest run` | 192 passed (17 файлов); прежние 34 теста карточки прошли под `AuthProvider` без правок заглушек. После вливания `main` с #24 — 197 passed |
| Типы и стиль фронта | `tsc --noEmit`, `eslint src`, `prettier --check` | чисто; предупреждений eslint не прибавилось |
| Бэкенд целиком | `pytest -q` на своей копии базы `cases_delui_tests` | 682 passed, 3 skipped на `main` после #23; после вливания `main` с #24 — 709 passed, 3 skipped (поставка бэкенд не меняет) |
| Фазовый гейт | `python3 scripts/delivery_check.py --diff-base origin/main` | 0 ошибок |
| Гейты формы | `pre-commit run --all-files` | все хуки зелёные; на pre-push гейт копипаста поймал клон-пару кнопок подтверждения (`DeleteProject.tsx` ↔ `DeleteUser.tsx`) — вынесена в `components/ConfirmDelete.tsx` |
| CI на ветке поставки | GitHub Actions, PR #25, коммит 17117fc | delivery, gates, tests — pass: https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36047944497 |

id примеров сначала были `PD1`–`PD8`; гейт читает id как одну заглавную букву
с цифрами и `PD1` не опознал (ошибка на фазе verify). Переименованы в `K1`–`K8`
двумя коммитами — спека (b2e78bd), потом тесты (929ea3e), — чтобы проверка
порядка «пример раньше теста» не ослепла; настоящий порядок виден по коммитам
c637f68 (спека) → f8179ae (красные тесты) → 92f1556 (код).

## Исполнение рисковых путей

`web/src/pages/card/DeleteProject.tsx` — удаление с подтверждением кнопкой в
браузере. Исполнено: боевая сборка ветки `vite build` (`index-B76zxvTz.js`,
`index-nsjzGzL1.css`), `vite preview` с прокси `/api` на `uvicorn
ahrefs_cases.api.main:app` из ветки поверх копии дев-базы `cases_delui_check`
(75 проектов, 29 прогонов) с копией каталога выгрузки (468 файлов); headless
Chrome 154 по CDP, окно 1400×1000, тема — переключателем приложения, светлая
и тёмная на каждом шаге (`scratchpad/ui/check.mjs`), at=2026-09-24.

| Шаг | Что на экране |
|---|---|
| K1: сотрудник (группа user) на карточке `lonelyplanet.com` | кнопки нет, карточка кончается сноской |
| K2: инженер, «Удалить проект» | «Удалить lonelyplanet.com? Вернуть его будет нельзя. Уйдут: точек рядов: 104 — за них платили, повторная загрузка купит их заново; вердиктов: 1; кейсов: 10; файлов PDF: 3. Останутся: строк журнала прогонов: 4 …; расход units. В свежей пачке есть кейс этого проекта…» |
| K2 у второй кампании `nordvpn.com` | «…файлов PDF: 0 … другие кампании этого сайта: 1 — у них свои данные» (все 5 PDF общие со второй кампанией, Z39) |
| K3: «Отмена» | подтверждение закрыто, проект на месте |
| K4: «Да, удалить» | карточка сменилась итогом «Проект lonelyplanet.com удалён» с числами ответа; ссылка ведёт на `/projects`; в копии базы строк обоих удалённых проектов 0, `run_items` без ссылки 8, `units_ledger` 590 строк и 27 366 units — как до удалений; с диска ушли 3 PDF `lonelyplanet.com`, файлы `nordvpn.com` на месте |
| K5: прогон 1089 переведён в `running`, удаление `machinemfg.com` | «прогон 1089 ещё идёт (running): он пишет строки проектов — удалите проект, когда прогон закончится» красным в подтверждении; проект на месте; статус возвращён |
| K6: «Пользователи» | «удалять проекты» у инженеров и админов, ключа `delete_projects` на экране нет |
| K7: прогон 1088, «?» | «lonelyplanet.com (проект удалён)» в строке «пропущен: нет данных»; «без замечаний собрано: 57, из них проектов удалено: 1» |
| K8: «Кейсы» | у пачки жёлтое предупреждение «в пачке кейс удалённого проекта — пересоберите кейсы, и архив соберётся без него»; «Скачать ZIP» недоступна, «Пересобрать кейсы» доступна |

Все 18 снимков (9 шагов × 2 темы) просмотрены глазами: тексты читаются в обеих
темах, подтверждение и итог не наезжают на соседние блоки. Первый заход снимал
страницу целиком и рисовал прибитые шапку и меню посреди листа — дефект снимка,
не экрана; снимки переделаны окном с блоком по центру.

Проход повторён на итоговом коде — после вливания `main` с #24 и выноса пары
кнопок в `components/ConfirmDelete.tsx` (сборка `index-DoCNIUPC.js`), на свежей
копии базы: K1–K8 те же, копия базы после — строк удалённых проектов 0,
`run_items` без ссылки 8, `units_ledger` 590 строк и 27 366 units.

Копии базы (`cases_delui_check`, `cases_delui_tests`), каталога выгрузки и
профиля Chrome удалены, процессы остановлены.

## Ревью рисковых мест

**Деньги.** Экран удаляет оплаченные ряды без возврата. Поэтому `AskAndDelete`
не даёт нажать «Да, удалить», пока не пришёл предпросмотр (`fetchDeletion`):
человек подтверждает числа — «точек рядов: N — за них платили, повторная
загрузка купит их заново», — а не кнопку. Числа только сервера (`Consequences`,
`ProjectDeleted` печатают поля ответа как есть, L78). Пересборки пачки экран
сам не запускает: `PackCard` по `outdated` выключает «Скачать ZIP» и оставляет
кнопку пересборки человеку.

**Безопасность.** Кнопка — по `can('delete_projects')` из `/api/auth/me`, а
`/me` с #23 отдаёт итог прав с личными решениями. Сервер проверяет право сам;
экран отстаёт от отозванного права до перезагрузки страницы (Z44) — на этот
случай отказ `403` приходит уже на предпросмотре, текст сервера показан, «Да,
удалить» недоступна (тест K5 про предпросмотр).

**Новый модуль.** `card/DeleteProject.tsx`: `DeleteProject` зовёт `useAuth` и
рисует `AskAndDelete` только при праве — хуки запросов живут внутри него, их
порядок не зависит от условия. `useDeletedProject` держит итог и чистит кэш:
`removeQueries(['project', id])` — иначе «назад» показал бы удалённую карточку
из кэша (`staleTime` 30 с), `invalidateQueries` для `projects`, `cases`, `runs`.
`ProjectCardPage` стал обёрткой над `ProjectCard`: после удаления карточка
снимается целиком вместе с запросами вложенных блоков (`CasePdf`), и повтор не
упирается в `404`.

**Журнал.** `Collected` считает удалённых среди собранных, `TroubleTable`
подписывает строку по признаку строки (`fate.project_deleted`), а не по домену:
у двух кампаний одного сайта домен один (K7 держит живую кампанию без пометки).

## Чего проверка НЕ доказывает

- Поведения на проде: там один пользователь, и право у него по группе engineer;
  путь «право отобрали, пока вкладка открыта» (Z44) виден только тестом.
- Мобильной ширины: снимки — окно 1400 px; подтверждение — обычный блок
  потока, у него нет фиксированной ширины.

## Spec coverage gaps

- Нет.

## Verdict
- [x] READY FOR HANDOFF — ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Дайджест утверждений


База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **31**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
K1	expect(screen.queryByRole('button', { name: 'Удалить проект' })).toBeNull();
K1	expect(seen.some((call) => call.endsWith('/deletion'))).toBe(false);
K2	expect(ask).toHaveTextContent('точек рядов: 116');
K2	expect(ask).toHaveTextContent('повторная загрузка купит их заново');
K2	expect(ask).toHaveTextContent('вердиктов: 1');
K2	expect(ask).toHaveTextContent('кейсов: 11');
K2	expect(ask).toHaveTextContent('файлов PDF: 5');
K2	expect(ask).toHaveTextContent('строк журнала прогонов: 4');
K2	expect(ask).toHaveTextContent('другие кампании этого сайта: 1');
K2	expect(ask).toHaveTextContent('пачка кейсов не скачается до пересборки');
K3	expect(screen.queryByRole('button', { name: 'Да, удалить' })).toBeNull();
K3	expect(seen.some((call) => call.startsWith('DELETE'))).toBe(false);
K3	expect(screen.getByText('klinika.example')).toBeInTheDocument();
K4	expect(seen).toContain('DELETE /api/projects/7');
K4	expect(done).toHaveTextContent('файлов PDF: 4');
K4	expect(done).toHaveTextContent('строк журнала прогонов: 4');
K4	expect(screen.queryByText('Почему эта группа')).toBeNull();
K4	expect(window.location.pathname).toBe('/projects');
K5	expect(await screen.findByText(detail)).toBeInTheDocument();
K5	expect(screen.getByText('Почему эта группа')).toBeInTheDocument();
Z44	expect(await screen.findByText(detail)).toBeInTheDocument();
Z44	expect(screen.getByRole('button', { name: 'Да, удалить' })).toBeDisabled();
Z44	expect(seen.some((call) => call.startsWith('DELETE'))).toBe(false);
K8	expect(await screen.findByText(note)).toBeInTheDocument();
K8	expect(screen.getByRole('button', { name: 'Скачать ZIP' })).toBeDisabled();
K8	expect(screen.getByRole('button', { name: 'Пересобрать кейсы' })).toBeEnabled();
K7	expect((await screen.findByText('первая')).closest('tr')).toHaveTextContent('(проект удалён)');
K7	expect(screen.getByText('вторая').closest('tr')).not.toHaveTextContent('(проект удалён)');
K7	expect(screen.getByText(/без замечаний собрано: 2/)).toHaveTextContent(
K6	expect(await screen.findByText('удалять проекты')).toBeInTheDocument();
K6	expect(screen.queryByText('delete_projects')).toBeNull();
```

✅ **Каждое утверждение ведёт к примеру спеки** (K1 K2 K3 K4 K5 K6 K7 K8 Z44), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 14 code (+9 process docs) / +489/-32 (net +457) |
| commits | 11 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | no — оракулы дописаны в существующие файлы тестов; урок L216 про запуск фазового гейта после спеки |
| implement_retries | 2 — гейты формы: функция `ProjectCardPage` вышла за 80 строк (стала обёрткой над `ProjectCard`), клон-пара кнопок подтверждения (вынесена в `ConfirmDelete`) |
| verify_fails_before_green | 0 в CI; локально фазовый гейт не опознал id `PD1`–`PD8` (переименованы в `K1`–`K8`, урок L216) |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
