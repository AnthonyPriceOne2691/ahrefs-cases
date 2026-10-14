# Verify report: brief-auto-list

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M145, M146 (repro) | `card-brief.test.tsx` на прежних `Brief.tsx`, `BriefForm.tsx` из `main` | **до правки** — 2 красных (пустой бриф — одна строка; в форме «не выбрано», подсказок нет); после — зелёные |
| M144 | `tests/test_brief_known.py`, `tests/test_api_project_brief.py` — источник рядом с правилом, каталог | `AUTOFILL` — те же пункты, что подставляет правило, и «Кто подготовил»; `/api/brief-fields` — 10 пунктов с `autofill`, 12 без |
| M145, M146 | vitest `card-brief.test.tsx` | 13 passed: пустой бриф — пункты сервиса со значениями, без значения — источник серым, «Остальные 3 пункта заполняет специалист.»; форма — «Сервис подставит: …» пунктом пустого значения у списка, подсказкой у текста; сохранение без правок шлёт `fields: {}` |
| Полный сьют | `pytest` (дев-база) | 951 passed, 12 skipped (4 мин 32 с) |
| Фронт | `vitest`, `tsc --noEmit`, ESLint, Prettier | 259 passed; чисто |

## Исполнение рисковых путей

- `web/src/pages/card/Brief.tsx`, `web/src/pages/card/BriefForm.tsx` — стенд (база `cases_geo`, API перезапущен на коде
  ветки), Chrome 1440 px, zooplus.de с пустым брифом: «Сервис заполняет сам, пока пункт пуст:» — отдел «SEO (по
  услуге из файла)», тип услуги, вид проекта, тематика, бюджет «150 (объём работ из файла)», срез, период 1, весомость;
  серым — «Кто подготовил: подпишется тот, кто сохранит бриф», «Тип сайта: по нише из файла, если она называет тип»;
  «Остальные 12 пунктов заполняет специалист.» Форма «Заполнить бриф» — в 10 полях «Сервис подставит: …» или «Сервис:
  …», значения полей пусты; закрыта «Отменой», ничего не сохранено. at=2026-10-14
- Прод до правки (чтение, 14.10): `brief_known` у всех 13 карточек с кейсом — 7–8 пунктов; все 13 PDF пачки
  `кейсы-2026-10-14.zip` (пересборка №39) — те же 7–8 подстановок; бриф у всех пуст — экран их не показывал.

## Что нашла проверка

- **Дефект был на экране, а не в данных:** сервер и PDF подставляли с 13.10, карточка пустого брифа писала одну
  строку, форма — «не выбрано». Тесты экрана с #72 проверяли подстановку только у частично заполненного брифа.
- **Подпись под полем владелец не увидел бы** — его снимок формы показывает «не выбрано»: подстановка стоит в самом
  поле, а не под ним.
- **Токен стенда истёк** (вчерашний) — Chrome показал форму входа; перевыпущен кодом сервиса в файл 600.

## Ревью рисковых мест

**Данные.** Миграций нет. Подстановка в бриф не пишется: в форме это текст пустого пункта списка и подсказка поля, а
не значение; сохранение без правок шлёт пустой набор полей (M146).

**Деньги.** Units не тратятся.

**Безопасность.** Новых путей и прав нет: каталог открыт тем же правом `read`, `brief_known` — в той же карточке.

**Интеграция.** `/api/brief-fields` — новое поле `autofill` у каждого пункта; экран без него (старый сервер) ведёт
себя как прежде — одной строкой.

## Чего проверка НЕ доказывает

- Прод: экран на настоящих карточках — после выкатки (jupid.com: 7 значений, «Кто подготовил», «Тип сайта» и «Бюджет»
  серым).

## Verdict
- [x] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **24**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
M144	assert len(autofill) == 10
M144	assert len(fields) - len(autofill) == 12
M144	assert autofill["department"] == "по услуге из файла"
M144	assert autofill["prepared_by"] == "подпишется тот, кто сохранит бриф"
M144	assert autofill["site_type"] == "по нише из файла, если она называет тип"
M144	assert autofill["budget"] == "объём работ из файла, если он указан"
M144	assert "client_request" not in autofill
M144	assert set(AUTOFILL) == set(full) | {"prepared_by"}
M144	assert all(AUTOFILL.values())
M144	assert AUTOFILL["department"] == "по услуге из файла"
M144	assert AUTOFILL["prepared_by"] == "подпишется тот, кто сохранит бриф"
M145	expect(await screen.findByText('Сервис заполняет сам, пока пункт пуст:')).toBeInTheDocument();
M145	expect(screen.getByText('Путешествия (по нише «путешествия»)')).toBeInTheDocument();
M145	expect(screen.getByText('120 (объём работ из файла)')).toBeInTheDocument();
M145	expect(screen.getByText('подпишется тот, кто сохранит бриф')).toBeInTheDocument();
M145	expect(screen.getByText('Остальные 3 пункта заполняет специалист.')).toBeInTheDocument();
M145	expect(screen.queryByText(/пунктов для специалиста/)).not.toBeInTheDocument();
M145	expect(screen.queryByText('Языковые версии')).not.toBeInTheDocument();
M146	expect(topic.value).toBe('');
M146	expect(topic.options[0]?.text).toBe('Сервис подставит: Путешествия (по нише «путешествия»)');
M146	expect(screen.getByLabelText('Бюджет проекта / объём работ')).toHaveAttribute(
M146	expect(screen.getByLabelText('Кто подготовил информацию по кейсу')).toHaveAttribute(
M146	expect(screen.getByLabelText('Языковые версии')).not.toHaveAttribute('placeholder');
M146	expect(sent).toEqual([{ fields: {} }]);
```

✅ **Каждое утверждение ведёт к примеру спеки** (M144 M145 M146), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 10 code (+18 process docs) / +252/-56 (net +196) |
| commits | 2 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | no — новые примеры в прежних оракулах (`test_brief_known.py`, `test_api_project_brief.py`, `card-brief.test.tsx`) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
