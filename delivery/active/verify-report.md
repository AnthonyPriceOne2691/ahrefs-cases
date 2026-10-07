# Verify report: screenshots-screen

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M60 | `tests/test_api_screenshots.py` | 7 passed (с прежними M48–M53) |
| M61–M63, M65–M67 | `web/src/pages/__tests__/card-screens.test.tsx` (подменный сервер: картинка байтами с типом, список после загрузки и удаления другой) | 6 passed |
| M64 | `web/src/pages/__tests__/shrink.test.ts` (холст и `createImageBitmap` подменены) | 4 passed |
| Оракулы — настоящие | мутанты: «скринов» убрано из окна удаления; блок считает правом всех | M66 красный; M61 красный; код возвращён |
| Прежний экран | весь фронтовый сьют | 23 файла, 234 passed; ESLint и `tsc` чистые |
| Живой проход | стенд: API и Vite на коде ветки, Chrome по CDP, карточка `brief-ok.example.com` | две миниатюры `data:image/png`; вид «Видимость в ИИ», подпись, снимок 2880 × 2000 PNG 5,5 МБ — ужат браузером, на сервере 2000 × 1389 (1 116 КБ), загрузка 1,2 с; «Удалить» → «Да, удалить» — скрин пропал, на сервере снова 2; окно удаления проекта: «…файлов PDF: 4; скринов: 2.», «Отмена» его закрыла |
| CSP прода | продакшен-сборка (`vite build` → `vite preview` на 127.0.0.1), заголовок из `deploy/nginx.conf` подставлен в документ через CDP `Fetch` | миниатюры `data:` загрузились (ширина 1440); контроль — та же картинка `blob:`-адресом: отказ, в журнале браузера нарушение `img-src` |

## Исполнение рисковых путей

- `web/src/pages/card/shrink.ts` — прогнал `node step13.mjs` (Chrome по CDP на стенде: вид и подпись
  родными событиями, файл в `input[type=file]` через `DOM.setFileInputFiles`), увидел: PNG 2880 × 2000
  весом 5,5 МБ ушёл ужатым — `createImageBitmap` и холст настоящего браузера дали JPEG, сервер принял его
  (201) и хранит 2000 × 1389; без ужатия тело в 5,5 МБ получило бы отказ по пределу 2,5 МБ. at=2026-10-07

## Ревью рисковых мест

**Безопасность.** Картинка берётся запросом с токеном (`download`), а не ссылкой: `<img src="/api/…">`
ушёл бы без `Authorization`. Миниатюра — `data:`-адрес: `reader.readAsDataURL(blob)`; `blob:` CSP прода
режет (проверено контролем). Загрузка и удаление — кнопки только у `can('edit_briefs')`, но решает сервер:
`require_right("edit_briefs")` на обоих эндпоинтах (M51). Новый `GET /api/screenshot-rules` — под
`require_right("read")`, отдаёт только константы.

**Сеть и прокси.** Больше предела не отправляется: `if (image.size <= maxBytes) return image;` — иначе
ужатие, и `if (smaller.size > maxBytes)` — отказ до запроса. Так ответ `413` не умирает на прокси.

**Ошибки.** Ответ правил и списка проверяется формой: `throw new Error('правила скринов пришли не той
формы')` — блок говорит об этом, карточка на месте (M67). Нераскодируемый файл — отказ словами, а не текст
браузера: `throw new Error('файл не открылся как картинка — нужен PNG, JPEG или WebP', { cause })`.

**Деньги.** Риска нет, потому что экран скринов не зовёт сбор и смету: запросы — только
`/api/screenshot-rules`, `/api/projects/{id}/screenshots` и `/api/screenshots/{id}`; units не тратятся.

**Производительность.** Миниатюра грузится один раз на `id` (`staleTime: Infinity`) — картинка по `id`
не меняется; после удаления её кэш снимается `removeQueries`. Ужатие идёт только для файла больше предела.

## Чего проверка НЕ доказывает

- Прокси прода (3 МБ) и его CSP вживую — проверка после выкатки (`observe_signal`); на стенде CSP
  подставлен в продакшен-сборку, прокси нет.
- Ужатие в Safari и Firefox — проверен Chrome.
- Снимок, который и после ужатия больше 2,5 МБ, вживую не встречен — ветка проверена тестом M64.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **29**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M60	assert rules.status_code == 200
M60	assert rules.json() == {
M60	assert client.get("/api/screenshot-rules").status_code == 401
M61	expect(first.getAttribute('src')).toMatch(/^data:image\/png;base64,/);
M61	expect(second.getAttribute('src')).toMatch(/^data:image\/png;base64,/);
M61	expect(screen.getByText('Видимость в ИИ · ChatGPT')).toBeInTheDocument();
M61	expect(screen.queryByRole('button', { name: 'Загрузить скрин' })).toBeNull();
M61	expect(screen.queryByRole('button', { name: /Удалить скрин/ })).toBeNull();
M67	expect(
M67	expect(screen.getByText('Бриф для копирайтера')).toBeInTheDocument();
M62	expect(await screen.findByAltText('Видимость в ИИ · Perplexity')).toBeInTheDocument();
M62	expect(sent).toEqual([
M62	expect(screen.getByLabelText('Подпись')).toHaveValue('');
M63	expect(await screen.findByText(detail)).toBeInTheDocument();
M63	expect(screen.getByRole('button', { name: 'Загрузить скрин' })).toBeEnabled();
M65	expect(screen.queryByText('Отчёт Ahrefs · Обзор · Германия (DE)')).toBeNull(),
M65	expect(sent.map((item) => item.call)).toEqual(['DELETE /api/screenshots/1']);
M65	expect(screen.getByText('Видимость в ИИ · ChatGPT')).toBeInTheDocument();
M66	expect(ask).toHaveTextContent('файлов PDF: 1; скринов: 2.');
M66	expect(done).toHaveTextContent('файлов PDF: 1; скринов: 2.');
M64	expect(await fitForUpload(small, LIMITS)).toBe(small);
M64	expect(toBlob).not.toHaveBeenCalled();
M64	expect(shrunk.size).toBe(400_000);
M64	expect(drawn).toEqual([[0, 0, 2000, 1500]]);
M64	expect(context.fillStyle).toBe('#ffffff');
M64	expect(toBlob.mock.calls[0]?.[1]).toBe('image/jpeg');
M64	await expect(fitForUpload(bytes(3_000_000), LIMITS)).rejects.toThrow(TooBigError);
M64	await expect(fitForUpload(bytes(3_000_000), LIMITS)).rejects.toThrow(/больше 2,5 МБ/);
M64	await expect(fitForUpload(bytes(3_000_000), LIMITS)).rejects.toThrow(
```

✅ **Каждое утверждение ведёт к примеру спеки** (M60 M61 M62 M63 M64 M65 M66 M67), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 10 code (+17 process docs) / +828/-34 (net +794) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — web/src/pages/__tests__/card-screens.test.tsx (новый оракул), web/src/pages/__tests__/shrink.test.ts (новый оракул) |
| implement_retries | 2 — строка блока в `ProjectCard` перевела функцию за предел 80 строк (блок переехал в `Brief`); константа 2000 в `shrink.ts` — копия серверной (`max_side` в правилах) |
| verify_fails_before_green | 1 — ESLint: пустой `close() {}` в подмене и сложность подменного `fetch` в новых тестах |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
