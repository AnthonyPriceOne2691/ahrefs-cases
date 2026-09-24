# Verify report: project-deletion-api

**Date:** 2026-09-24
**Verifier:** human:anthony (приёмка); оракулы и исполнение на копии базы — agent:claude
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36027023060
**Commit:** e08012e

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| D1–D14 до правки | тестовый файл из коммита 40d9595 на дереве `origin/main` + `storage/locks.py` (`git archive` в scratchpad, своя копия базы) | 11 failed из 11: удаления нет (`405` вместо `200`/`403`/`404`/`409`), задача и пересчёт порогов замка не держат (`[True] == [False]`). В сообщении 40d9595 стоит «13»: столько тестов было до того, как справочник прав вошёл в тест прав, а два отказа — в один тест |
| Свёртка судеб до правки ключа | тот же тест D10 с полем `project_deleted`, но прежним ключом `_fold_by_project` по `project_id` | падал: `also-gone.delete.example` пропадал, два удалённых проекта прогона давали одну судьбу чужого домена |
| D1–D14 после правки | `pytest tests/test_api_projects_delete.py tests/test_jobs_mark_the_run.py` | 14 passed (11 новых и 3 прежних теста метки прогона — замок в них заглушён вместе с `_finish`) |
| Сьют целиком | `pytest -q` на своей копии дев-базы (`cases_delete_tests`) | 674 passed, 3 skipped (до правки на той же копии — 662 passed; единственное падение — ещё не созданный `repro_test` из STATUS) |
| Типы и стиль | `mypy src/ahrefs_cases`, `ruff check`, `ruff format --check` | чисто, 122 файла |
| Гейты формы | `pre-commit run --all-files` | 29 хуков, упавших 0 |
| Фазовый гейт | `python3 scripts/delivery_check.py --diff-base origin/main` | 0 ошибок |
| Исполнение на копии дев-базы | `eval-smoke.md`, ниже — «Исполнение рисковых путей» | D1–D14 подтверждены на настоящих строках стенда |
| CI на ветке поставки | GitHub Actions, PR #23, коммит e08012e | delivery, gates, tests — pass; сьют 675 passed, 2 skipped: https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36027023060 |
| Мутационный гейт | шаг CI `Mutation testing` | не судит: mutmut 3.8.0 выходит с кодом 1 на разборе конфига pytest — так же на соседней поставке (run 36024004057); вердикта по мутантам нет |
| Покрытие изменённых файлов | шаг CI `Diff coverage` (информационный до Z22, 29.09) | `rulesets.py` 65,1 %, `runs.py` 68,8 % — покрытие файла целиком; строки поставки исполняются тестами: локально по трём модулям тестов `rulesets.py` 90 %, `runs.py` 96 %, `removal.py` 94 %, `locks.py` 100 %, новые строки `projects.py` — все |

**Полный прогон на общей дев-базе был красным не по диффу — и это записано.**
Первый прогон (18:38–18:40, код `origin/main`, до правок) дал 3 failed и
ошибку сторожа: `test_api_read` не входил (`401`, `KeyError: access_token` —
учётки сносила уборка соседа), `test_cases_after_the_second_button_are_downloadable`
видел «устаревшими» кейсы стенда, а `stand_verdicts_survive_the_suite` поймал
вердикты стенда версии `0.0.0-default`, переписанные LIVE → FIXTURE. В то же
время на той же базе шёл сьют соседнего worktree: `isolated_ruleset` одного
возвращает стенду действующую версию, пока задача другого классифицирует
(координатор подтвердил параллельные прогоны). Повтор того же сьюта на своей
копии базы — 662 passed, падений нет; все прогоны поставки после этого — на
копии. **Вердикты дев-стенда остались переписанными**: FIXTURE у 75 из 75, живые
ряды есть у 57 проектов — восстанавливается бесплатной переклассификацией по
живым рядам, решение за владельцем стенда.

## Исполнение рисковых путей

`src/ahrefs_cases/export/removal.py` — удаление на живой базе и файлы на диске.
Исполнено `uvicorn ahrefs_cases.api.main:app --port 8765` из worktree поверх
копии дев-базы `cases_delete_check` (75 проектов, 1808 кейсов, 590 строк
расхода) с каталогом выгрузки — копией `data/out` (468 файлов) и тем же
относительным `EXPORT_OUTPUT_DIR=./data/out`, что у дев-стенда; сценарий —
`scratchpad/verify/check.py`, at=2026-09-24.

| Проект | Ответ удаления | По таблицам | На диске |
|---|---|---|---|
| `nordvpn.com` #13039 (кампания 1 из 2) | `116 точек, 1 вердикт, 11 кейсов, files 0, run_items 4, twin 1, pack_blocked false` | −1 / −116 / −1 / −11 / −11; `run_items` 578 → 578, без ссылки +4 | 0: все 5 PDF общие со второй кампанией (Z39) |
| `nordvpn.com` #13040 (кампания 2) | `…files 5, twin 0, pack_blocked true` | −1 / −116 / −1 / −11 / −11 | −5 |
| `legal-partners.pl` #915 (24 строки журнала) | `260 точек, 2 вердикта, 92 кейса, files 21, run_items 24` | −1 / −260 / −2 / −92 / −92 | −21 |

Предпросмотр совпал с ответом удаления у всех трёх. `runs` 29 → 29,
`units_ledger` 590 строк и 27 366 units до и после каждого удаления. Карточка
и повторное удаление `legal-partners.pl` — `404`. Судьбы прогона 1088: две
строки `nordvpn.com` по 132 units → после удаления обеих кампаний одна «ok,
264, удалён» (граница Z41).

Пачка, собранная командой `run_collect.py pack` на копии: до удалений
`outdated: null`; после первой кампании `nordvpn.com` — по-прежнему отдаётся
(сумма её PDF осталась у второй, Z39); после второй — `outdated:
project_deleted`, скачивание `409` «в пачке кейс удалённого проекта —
пересоберите кейсы, и архив соберётся без него».

Гонки — настоящим воркером RQ (`SimpleWorker`: разветвляющийся work-horse RQ на
macOS падает SIGSEGV до начала задачи, прогон 1813 так и остался `queued`; на
Linux прода этого нет), прогон 1814 из `POST /api/runs`, `DELETE` каждые 50 мс
(`scratchpad/verify/race.py`):

| t, с | Прогон | Удаление |
|---|---|---|
| 0,03 | `queued` | `409` «прогон 1814 ещё идёт (queued)…» |
| 0,40 | `running` | `409` «прогон 1814 ещё идёт (running)…» |
| 0,46 | `done` — хвост задачи идёт | `409` «сервис дописывает результаты по проектам…» |
| 0,61 | `done` | `200` |

Прогон 1814 остался `done`, 72 из 72, ошибки нет. Копия базы, копия каталога
и ключи проверки в Redis (db 5) после проверки удалены.

## Ревью рисковых мест

**Транзакция БД.** `delete_project` держит `hold_start` и исключительный
`work_is_idle` до `session.commit()`; `removal.delete_rows` — один `DELETE` по
`projects`, остальное уносит каскад схемы (`cases.verdict_id` на `RESTRICT`
проверяется после каскада — на копии 92 кейса и 2 вердикта ушли одним
оператором). Файлы — после коммита: `own_files` спрашивает ссылки уже в новой
транзакции, `remove_files` в потоке. Откат до коммита оставляет и строки, и
файлы.

**Гонки.** Замок работы: задача держит `work_lock` в `_run_guarded` на всё
`await work` — хвост после `finish_run` (`share_twin_points`, `classify_all`)
тоже под ним; пересчёт порогов — `hold_work` на свою транзакцию. Удаление
пробует исключительно и не ждёт. Прогон в `queued`/`running` — отдельной
проверкой под тем же `hold_start`, что `_enqueue`: между проверкой и удалением
новый прогон не встанет. Сессионный замок — на своём `NullPool`-соединении с
`AUTOCOMMIT`: не утекает в пул и не держит транзакцию часами. Не прикрыты
консольные команды — Z41.

**Деньги.** `units_ledger` не трогается ни каскадом, ни кодом (ссылки на проект
у него нет); строка журнала прогонов остаётся с доменом и units
(`ON DELETE SET NULL`). Удаление посреди прогона раньше роняло `store_history`
на внешнем ключе до `record_spend` — теперь ему отказано.

**Безопасность (права).** `_MANAGING` добавляет `delete_projects` engineer и
admin; проверка — `require_right` через `rights_of_user`, личное «Нет»
отбирает, «Да» выдаёт (D6). `/me` и вход теперь отдают тот же итог — прежде
набор группы. Предпросмотр под тем же правом: чужому не показывает, что
лежит за проектом.

**Файлы на диске.** `_unshared` сверяет разрешённые пути: относительный
`data/out/…` дев-стенда и абсолютный путь прода — один файл. Вне каталога
выгрузки не трогается ничего (лог `project_file_outside_output`), общий с
артефактом другого проекта — тоже; ошибка `unlink` — лог
`project_file_not_removed`, удаление не падает.

**Пачка.** `holds_deleted_case` читает архив целиком (`packed_checksums`) — на
пачке в 60 PDF 2,4 МБ это миллисекунды; нечитаемый архив — «не знаю», отдаётся,
как раньше (прежние тесты пачки на заглушечном ZIP зелёные).

**Производительность.** `.all()` в `trace_of` — артефакты одного проекта (на
копии максимум 92 у `legal-partners.pl`); `own_files` спрашивает только
имена файлов этого проекта, `holds_deleted_case` — только суммы одной пачки.
Под замками постановки и работы удаление держится миллисекунды плюс чтение
пачки; очередь за ним встаёт только у `_enqueue`.

**Журнал.** `_fate_key` — `project_id`, а у пустой ссылки `raw_domain`: ключи
разных типов не пересекаются; счётчики прогона хранятся в `runs` и не
пересчитываются.

## Предупреждение фазового гейта

`delivery_check` предупреждает (§3.1d), что у D14 порядок «пример → тест» не
проверить. Предупреждение ложное по истории: id `D14` уже был в спеке и тестах
старой поставки (коммит 842ce19), и первый коммит с ним у обоих путей один. У
этой поставки порядок виден коммитами: спека 445eb11, красные тесты 40d9595,
код e08012e.

## Чего проверка НЕ доказывает

- Что замок работы переживёт обрыв соединения посреди задачи: соединение
  упало — замок снят, и задача продолжит без него. Удаление в этот момент
  возможно; вероятность — рестарт Postgres посреди прогона.
- Поведение на Linux-воркере прода — проверено `SimpleWorker` на macOS; путь
  задачи тот же (`collect_job` → `_run_guarded`), отличие — только fork.
- Экран: вторая поставка. До неё справочник прав покажет ключ
  `delete_projects` без подписи.

## Spec coverage gaps

- D5 (файл вне каталога выгрузки) и D6 (матрица прав) — тестами; на копии
  базы таких артефактов и личных решений нет.

## Verdict
- [x] READY FOR HANDOFF — ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Дайджест утверждений


База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **36**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
D1	assert response.status_code == 200
D1	assert response.json() == {"project_id": stand.gone, **GONE_TRACE, "pack_blocked": False}
D1	assert set(writer(lambda s: _rows(s, stand.gone))[0].values()) == {0}
D1	assert not stand.files["own"].exists(), "свой PDF стирается вместе с кейсом"
D4	assert stand.files["shared"].exists(), "D4: на общий файл ссылается кейс соседа"
D5	assert stand.files["outside"].exists(), "D5: вне каталога выгрузки удаление не хозяйничает"
D2	assert writer(lambda s: _journal(s, stand.run)) == [(kept, ledger)]
D3	assert writer(lambda s: _rows(s, stand.twin)) == [twin_before]
D3	assert stand.files["twin"].exists()
D3	assert second.status_code == 200
D4	assert not stand.files["shared"].exists(), "D4: ничей файл уходит с последним кейсом"
D6	assert response.status_code == (200 if allowed else 403)
D6	assert ("delete_projects" in rights) is allowed
D6	assert by_group == {"engineer": True, "admin": True, "user": False}
D7	assert (response.status_code, response.json()["detail"]) == (404, "проекта 0 нет")
D8	assert (by_run.status_code, by_tail.status_code) == (409, 409)
D8	assert f"прогон {stand.run}" in by_run.json()["detail"]
D8	assert "через минуту" in by_tail.json()["detail"]
D8	assert writer(lambda s: _rows(s, stand.gone))[0]["points"] == 3
D8	assert client.delete(gone, headers=headers).status_code == 200
D9	assert (response.status_code, seen) == (200, [False])
D14	assert seen == [False]
D14	assert await _work_is_free(), "после задачи замок свободен"
D10	assert client.delete(f"/api/projects/{project}", headers=headers).status_code == 200
D10	assert fates == [
D10	assert (card["projects_total"], card["projects_ok"], card["units_actual"]) == (3, 2, 50)
D11	assert client.get("/api/cases/pack", headers=headers).json()["outdated"] is None
D11	assert client.get("/api/cases/pack/download", headers=headers).status_code == 200
D11	assert preview.json() == {"project_id": stand.gone, **GONE_TRACE, "pack_blocked": True}
D11	assert files["own"].exists(), "предпросмотр ничего не удаляет"
D11	assert client.get(f"{gone}/deletion", headers=_headers(client, CLERK)).status_code == 403
D11	assert client.delete(gone, headers=headers).status_code == 200
D11	assert (state["outdated"], refused.status_code) == ("project_deleted", 409)
D11	assert "пересоберите" in state["note"]
D11	assert refused.json()["detail"] == state["note"]
D11	assert client.get("/api/cases/pack/download", headers=headers).status_code == 200
```

✅ **Каждое утверждение ведёт к примеру спеки** (D1 D10 D11 D14 D2 D3 D4 D5 D6 D7 D8 D9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 15 code (+11 process docs) / +861/-66 (net +795) |
| commits | 3 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_api_projects_delete.py (новый оракул) |
| implement_retries | 0 по оракулам — зелёные с первой правки кода; три захода ужатия диффа под предохранитель: net 1046 → 791 (тесты таблицами, докстринги короче) |
| verify_fails_before_green | 0 по коду; 1 полный прогон красный по окружению — параллельный сьют соседнего worktree на общей дев-базе (L211), повтор на своей копии базы зелёный; CI зелёный с первого прогона |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
