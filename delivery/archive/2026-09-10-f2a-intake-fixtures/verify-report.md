# Verify report

**Date:** 2026-09-10
**Verifier:** human:anthony
**asserts_reviewed_by:** human:anthony at=2026-09-10 — подписаны девять примеров B13–B21, дописанных по ходу implement
<!-- Дайджест даёт `asserts_without_example: 0`, и формально этого хватало бы
     для `n/a`. Но девять примеров (B13–B21) дописаны в спеку ПО ХОДУ implement,
     то есть после подписи `human_ok_spec` — «человек подписал заранее» про них
     неверно. Поэтому подпись здесь настоящая, а не n/a: читать нужно девять
     строк таблицы в spec.md, не сто утверждений. -->
**CI run:** quality на 8da09a5 — success (main-guard skipped, как на всех прямых пушах)
**Commit:** см. `git log` до открытия verify

## Прогон в чистом клоне

Локальные гейты обходятся (`commit -n`, `STRICT=0`), поэтому доказательством
служит склонированное состояние, а не рабочее дерево (§10.4).

```
$ git clone . <clone> && cd <clone>
$ python3 scripts/delivery_check.py
  delivery_check: 0 error(s), 0 warning(s)

$ python3 -m pytest -q
  116 passed, 1 skipped

$ python3 scripts/run_collect.py all config/projects.example.csv
  принято: 3 (создано 0, обновлено 3)
  прогон 3: done · проектов: 3 (собрано 3, пропущено 0, упало 0)
  точек записано: 100 · units потрачено: 150

$ ls AGENT_STACK.md CODE_QUALITY_GATES.md
  No such file or directory   # вариант D: тексты канонов в историю не уехали
```

Клон содержит механику (218 файлов) и не содержит текстов канонов.

## Shape oracles
- [x] PASS — `pre-commit run --all-files`: 27 хуков, упавших 0
- [x] PASS — `ruff check` / `ruff format --check` / `mypy --strict`: чисто на 68 модулях
- [x] PASS — гейты видят код: `check_gate_coverage` — 15 скриптов, подключено 11,
      осознанно не подключено 4 с причинами; `check_gate_value` — восемь гейтов «держим (ловит)»

## Behavior oracles
- [x] PASS — `pytest`: 116 тестов, 1 пропущен (цикл миграций — разрушающий, идёт в CI)
- [x] PASS — покрытие ядра **94 %** при пороге 80 % (§10 документа реализации)
- [x] PASS — `scripts/delivery_check.py`: 0 ошибок, 0 предупреждений
- [x] PASS — примеры B1–B21 закрыты тестами; дайджест: `asserts_without_example: 0`

## Product oracles
- [x] PASS — `delivery/active/eval-smoke.md`: сквозной путь прогнан на чистой дев-базе,
      включая повторный запуск (`создано 0, обновлено 3`) и два негативных случая
- [ ] n/a — `delivery/evals/smoke/` пуст: устойчивый smoke-набор заводится в Ф5,
      когда прогон станет запускаться по HTTP, а не командой разработчика

## Что нашлось на verify, а не раньше

- **CI упал на коммите 8ec7020, и я этого не заметил**, продолжив писать код.
  Причина: шаг «Canon payload selftest» ищет строку `stack-selftest:` в
  `delivery/active/STATUS.md`; в Ф1 она стояла абзацем прозы в разделе «Волна В1
  пройдена» и при открытии Ф2а не переехала. Починено (`8da09a5`), объявление
  теперь поле STATUS. **Урок шире случая:** объявление, живущее прозой, теряется
  при первом же переносе поставки.
- **Дайджест утверждений: 69 без id примера.** Это не «тесты плохие», а честный
  счёт: девять содержательных ожиданий были придуманы по ходу и в спеке
  отсутствовали. Дописаны как B13–B21 и требуют подписи (см. ниже), остальные
  привязаны к существующим примерам.

## Порядок «пример → тест» у B13–B21

`delivery_check` предупреждает честно: девять примеров приехали тем же коммитом,
что и тесты, поэтому **порядок не доказан**. Так и было: ожидания сформулированы
по ходу implement, а не до кода. Признаётся, а не обходится — отсюда настоящая
подпись под дайджестом вместо `n/a`.

Что из этого следует для Ф2б: спека коммитится отдельным коммитом до первой
строки кода. Тогда порядок виден в истории, а не в объяснении.

## Spec coverage gaps
- Ф2б (кэш закрытых месяцев, инкрементальный `date_from`, single-flight, смета,
  preflight квоты, шаг 2 воронки) — вынесена сознательно, см. «Граница с Ф2б» в STATUS.
- `AhrefsLive` написан, но проверен только на подменённом транспорте. Живой API
  не проверяет никто до Ф7 — это объявлено в спеке и в §1a документа реализации.
- Оси ③ OKF и ⑤ оракулы модели не развёрнуты: волна В2 приходит после Ф3,
  В3 — перед LLM-веткой. `docs/CONTOUR_ROLLOUT.md`.

## Verdict
- [x] READY FOR HANDOFF
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

Поставил Verifier `human:anthony`, 2026-09-10.

Принято с двумя объявленными пробелами: `AhrefsLive` проверен только на
подменённом транспорте (живой API — Ф7) и `delivery/evals/smoke/` остаётся
пустым до Ф5, когда прогон станет запускаться по HTTP.
## Assertion digest (ревью ожиданий, не кода)

База: `8ec7020` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **111**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
B7	assert [(p.at, p.values) for p in first] == [(p.at, p.values) for p in second]
B7	assert _traffic(first) != _traffic(second)
B7	assert _traffic(first) != _traffic(second)
B8	assert len(points) == shape.months - len(shape.holes)
B8	assert all(value > 0 for value in _traffic(points))
B9	assert len(points) == SHAPES[ScenarioName.SHORT_HISTORY].months
B19	assert traffic[-1] < max(traffic)
B19	assert traffic[-1] < traffic[-3]
B19	assert refdomains[-1] / refdomains[0] > 3.0
B19	assert traffic[-1] / traffic[0] < 2.0
B10	assert result.source == MetricSource.FIXTURE
B10	assert set(result.points[0].values) == {Metric.ORG_TRAFFIC, Metric.ORG_COST}
B10	assert metrics.units_actual == METRICS_HISTORY.estimate_units() == 50
B10	assert refdomains.units_actual == REFDOMAINS_HISTORY.estimate_units() == 5
B11	assert result.is_empty
B11	assert result.units_actual == 0
B6	assert len(result.points) == 6
B6	assert all(point.at >= date(2026, 1, 1) for point in result.points)
B20	assert table.scenario_for("d47.example.com") is ScenarioName.LATE_DROP
B20	assert table.scenario_for("EMPTY.example.com") is ScenarioName.EMPTY
B20	assert table.scenario_for("клиент.рф") is table.default
B20	assert isinstance(table, ScenarioTable)
B20	assert table.scenario_for("any.example.com") is table.default
B6	assert report.status == RunStatus.DONE.value
B6	assert report.projects_total == DOMAINS
B6	assert report.projects_ok == DOMAINS
B6	assert points == report.points_written > DOMAINS
B10	assert len(rows) == DOMAINS
B10	assert {row.endpoint for row in rows} == {METRICS_HISTORY.name}
B10	assert {row.kind for row in rows} == {LedgerKind.SPENT}
B10	assert all(row.units_estimated == row.units_actual for row in rows)
B10	assert report.units_spent == DOMAINS * METRICS_HISTORY.estimate_units() == 5000
B11	assert report.status == RunStatus.DONE.value
B11	assert (report.projects_ok, report.projects_skipped) == (1, 2)
B11	assert all(item.reason for item in skipped)
B11	assert all(item.units_actual == 0 for item in skipped)
B9	assert item.outcome is RunItemOutcome.OK
B9	assert "short_history" in item.reason
B21	assert first.points_written == second.points_written == total
B21	assert by_domain["d1.example.com"] is ProjectStatus.COLLECTED
B21	assert by_domain["empty.example.com"] is ProjectStatus.SKIPPED
B21	assert report.status == RunStatus.PARTIAL.value
B21	assert (report.projects_ok, report.projects_failed) == (2, 1)
B21	assert run.params_snapshot["provider"] == "fixture"
B21	assert run.params_snapshot["history_grouping"] == "monthly"
B21	assert run.params_snapshot["fixture_seed"] == 42
B18	assert (response.units_actual, response.units_estimated) == (63, 50)
B18	assert response.units_actual == 0
B18	assert calls["n"] == 2
B18	assert response.units_actual == 50
B18	assert calls["n"] == 1
B8	assert [point.at.isoformat() for point in result.points] == ["2025-01-01", "2025-02-01"]
B8	assert result.points[1].values == {Metric.ORG_TRAFFIC: 1200.0}
B8	assert result.source == MetricSource.LIVE
B18	assert seen["select"] == "date,org_traffic,org_cost"
B18	assert "paid_traffic" not in seen["select"]
B18	assert seen["history_grouping"] == "monthly"
B18	assert seen["mode"] == "subdomains"
B10	assert METRICS_HISTORY.estimate_units() == 50
B10	assert REFDOMAINS_HISTORY.estimate_units() == 5
B10	assert wide.estimate_units() == 60
B1	assert report.accepted == GOOD_ROWS
B1	assert report.created == GOOD_ROWS
B1	assert report.rejected_rows == len(BAD_ROWS)
B1	assert await _count_projects(db_session) == GOOD_ROWS
B1	assert expected in reasons, f"строка {row_no}: ожидали {expected}, получили {reasons}"
B5	assert again.created == 0
B5	assert again.updated == GOOD_ROWS
B5	assert await _count_projects(db_session) == GOOD_ROWS
B5	assert (project.work_volume, project.client) == (99, "Acme Renamed")
B5	assert report.created == 2
B5	assert await _count_projects(db_session) == 2
B5	assert report.created == 1
B5	assert RejectReason.DUPLICATE_IN_SOURCE in report.by_reason()
B5	assert project.notes == "вторая"
B15	assert report.accepted == 0
B15	assert report.by_reason() == {RejectReason.MISSING_COLUMN: 1}
B15	assert await _count_projects(db_session) == 0
B4	assert normalize_domain(raw) == expected
B4	assert isinstance(result, DomainRejected)
B4	assert result.reason == reason
B4	assert normalize_domain("https://www.example.com/") == normalize_domain("EXAMPLE.COM")
B4	assert (
B2	assert sheet is not None
B2	assert from_csv.columns == from_xlsx.columns == from_sheet.columns == tuple(HEADER)
B2	assert _as_tuples(from_csv) == _as_tuples(from_xlsx) == _as_tuples(from_sheet)
B17	assert table.columns == tuple(HEADER)
B17	assert _as_tuples(table)[0][0] == "example.com"
B3	assert _as_tuples(table)[1][3] == "Бейшпиль ГмбХ"
B3	assert decode("домен,клиент\nexample.com,Ромашка\n".encode()).startswith("домен")
B2	assert sheet is not None
B2	assert row.get("period_start") == "2025-01-01"
B2	assert row.get("work_volume") == "120"
B2	assert sheet_export_url(link) == expected
B1	assert not drafts
B1	assert reason in {item.reason for item in rejections}
B13	assert not rejections
B13	assert drafts[0].period_start == expected
B14	assert drafts[0].publishable is True
B14	assert drafts[0].publishable is False
B1	assert not rejections
B1	assert drafts[0].work_volume is None
B1	assert not rejections
B1	assert drafts[0].target_mode is TargetMode.SUBDOMAINS
B1	assert reasons == {RejectReason.BAD_DATE, RejectReason.BAD_GEO, RejectReason.BAD_FLAG}
B1	assert drafts[0].geo == "US"
B1	assert "источник: list.csv" in lines[0]
B1	assert "строка 2" in lines[-1]
B1	assert RejectReason.BAD_FLAG.value in lines[-1]
B15	assert not drafts
B15	assert [item.reason for item in rejections] == [RejectReason.EMPTY_SOURCE]
```

✅ **Каждое утверждение ведёт к примеру спеки** (B1 B10 B11 B13 B14 B15 B17 B18 B19 B2 B20 B21 B3 B4 B5 B6 B7 B8 B9), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base 8ec7020 -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 40 code (+5 process docs) / +3826/-67 (net +3759) |
| commits | 6 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_collect_fixtures.py (новый оракул), tests/test_collect_run.py (новый оракул), tests/test_collect_transport.py (новый оракул), tests/test_intake_accept.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
