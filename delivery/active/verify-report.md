# Verify report: brief-fields-api

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M14–M17 | `tests/test_storage_brief.py` | 14 passed |
| M18–M23 | `tests/test_api_project_brief.py` (своя запись, свои люди) | 6 passed; соседи `test_api_auth`, `test_api_users`, `test_api_read`, `test_migrations_match_models` — зелёные (60 вместе) |
| Сверка моделей с миграциями | `test_migrations_match_models` | `server_default` модели = миграции |
| Экран людей | vitest `users.test.tsx`, `users-manage.test.tsx` | 22 passed |
| Живой проход | стенд на свежей копии дев-базы (миграция `c0d1e2f3a4b5`), Chrome по CDP | «Пользователи»: значок «заполнять бриф» у всех групп, включая «пользователь», строки не поехали; из браузера `GET /api/brief-fields` — 200, 5 разделов, 22 поля; `PATCH` с «Маркетплейс» — 200, хранится `marketplace`; «адская» сложность — 422 «Сложность проекта: «адская» не из списка: Низкая, Средняя, Высокая, Очень высокая»; после `nda: true` на карточке — «публиковать без названия», после `nda: false` значок ушёл |

## Ревью рисковых мест

**Безопасность.** Новое право `edit_briefs` стоит зависимостью `require_right("edit_briefs")`
на `edit_brief`, а каталог — под `require_right("read")`; личное «Нет» отбирает правку (M23).
Ссылка на папку проходит только как https на `drive.google.com` / `docs.google.com` —
`_drive_link` сверяет `hostname`, а не подстроку, поэтому `drive.google.com.evil.example`
отклоняется (M16). Значения брифа в журнал не уходят: `brief_updated` пишет `sorted(patch.fields)`
— ключи, без значений.

**Транзакция БД.** `edit_brief` не пишет ничего, пока `_merged` не проверил все поля: отказ
поднимается до присваивания `project.brief`, а сессия `session_scope` откатывается на исключении —
годное поле того же запроса не записано (M21). Новый словарь вместо правки на месте — иначе
изменение внутри JSONB ORM не увидел бы.

**Интеграция — риска нет**, потому что `urllib` здесь только разбирает строку ссылки
(`urlsplit` в `_drive_link`): сервис по ней в сеть не ходит, ссылку открывает человек.

**Производительность — риска нет**, потому что каталог собирается из кортежа `FIELDS` в 22
элемента, а правка читает один проект по ключу (`session.get`).

**Новые модули.** `storage/brief.py` — данные и две чистые функции; `api/routers/briefs.py` —
два эндпоинта без состояния.

## Чего проверка НЕ доказывает

- Что списки «тип услуги», «вид проекта», «срез динамики» совпадут с листом шаблона
  агентства — это предложение до сверки, показано владельцу.
- Формы брифа на экране ещё нет (поставка 2б): бриф правится только через API.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **38**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
L80	assert response.status_code == 200
M18	assert response.status_code == 200
M18	assert catalog["sections"][0] == "Инфо о сотруднике"
M18	assert "Очень высокая" in [choice["label"] for choice in by_key["complexity"]["choices"]]
M18	assert by_key["folder_url"]["column"] == "folder_url"
M18	assert client.get("/api/brief-fields").status_code == 401
M19	assert response.status_code == 200
M19	assert response.json()["fields"] == stored
M19	assert _card(client, project_id)["brief"] == stored
M20	assert response.status_code == 200
M20	assert _card(client, project_id)["brief"] == {"goals": "топ-10"}
M21	assert response.status_code == 422
M21	assert "Сложность проекта" in detail
M21	assert "Папка проекта на Google Drive" in detail
M21	assert "nonsense" in detail
M21	assert _card(client, project_id)["brief"] == {}
M22	assert closed.json()["nda"] is True
M22	assert _card(client, project_id)["project"]["publishable"] is False
M22	assert _card(client, project_id)["project"]["publishable"] is True
M23	assert "edit_briefs" in rights.json()["rights"]
M23	assert _patch(client, project_id, {"nda": True}, email=REVOKED).status_code == 403
M23	assert _patch(client, 10**9, {"nda": True}).status_code == 404
M14	assert SECTIONS == (
M14	assert len(FIELDS_BY_KEY) == len(FIELDS)
M14	assert {field.section for field in FIELDS} == set(SECTIONS)
M14	assert (field.kind is FieldKind.CHOICE) == bool(keys), field.key
M14	assert len(keys) == len(set(keys)), field.key
M14	assert columns == [
M15	assert normalize(field, raw) == stored
M15	assert label_of(field, stored) != stored
M15	assert isinstance(result, BriefRejected)
M15	assert "«адская»" in result.detail
M15	assert "Очень высокая" in result.detail
M16	assert normalize(FIELDS_BY_KEY["folder_url"], raw) == raw
M16	assert isinstance(normalize(FIELDS_BY_KEY["folder_url"], raw), BriefRejected)
M17	assert normalize(field, "  рост заявок из органики  ") == "рост заявок из органики"
M17	assert normalize(field, "   ") == ""
M17	assert isinstance(normalize(field, "я" * (field.max_len + 1)), BriefRejected)
```

✅ **Каждое утверждение ведёт к примеру спеки** (L80 M14 M15 M16 M17 M18 M19 M20 M21 M22 M23), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 12 code (+16 process docs) / +742/-6 (net +736) |
| commits | 2 |
| time_to_accepted_spec | spec drafted, not yet accepted |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_api_project_brief.py (новый оракул), tests/test_storage_brief.py (новый оракул) |
| implement_retries | 1 — ruff format переписал `storage/brief.py` на первом коммите |
| verify_fails_before_green | 0 |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
