# Tasks: project-deletion-api

Уроки по затронутым путям — в `plan.md` (L8, L13, L49, L52, L57, L59, L63, L64,
L74, L78, L80, L85, L87, L88, L89, L101, L111, L125, L130, L142, L148, L150,
L151, L152, L153, L158, L159, L173, L174, L187, L202, L205, L206).

## Slice 1 — оракулы до кода

- [ ] T1: `tests/test_api_projects_delete.py` — D1–D11, D13 через HTTP на своих
      строках; D14 и замок пересчёта; падают до правки.

## Slice 2 — право и замки

- [ ] T2: `delete_projects` в `_GROUP_RIGHTS` (engineer, admin); вход и `/me`
      отдают итог `rights_of_user`.
- [ ] T3: `storage/locks.py`: ключ постановки прогона (переезд из `runs.py`),
      ключ работы; задача держит его в `_run_guarded`, пересчёт порогов — на
      транзакцию.

## Slice 3 — удаление

- [ ] T4: `export/removal.py`: след проекта, свои файлы, стирание после коммита.
- [ ] T5: `DELETE /api/projects/{id}` и `GET /api/projects/{id}/deletion`.

## Slice 4 — журнал и пачка

- [ ] T6: свёртка судеб по `project_id`, у удалённого — по домену;
      `project_deleted` в судьбе.
- [ ] T7: `newest_pack` и `packed_checksums` в `export/archive.py`; пачка с
      кейсом удалённого проекта — `outdated` в состоянии и `409` на скачивании.

## Slice 5 — проверка и сдача

- [ ] T8: исполнение на копии дев-базы (`eval-smoke.md`), копия удалена.
- [ ] T9: pytest, mypy, ruff, `delivery_check`, реестр находок (Z39–Z41),
      концепт в `knowledge/`, архив и урок (L210–L211), PR и зелёный CI.
