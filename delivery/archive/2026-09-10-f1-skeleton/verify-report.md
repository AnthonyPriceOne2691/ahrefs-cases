# Verify report

**Date:** 2026-09-10
**Verifier:** human:anthony
**asserts_reviewed_by:** human:anthony at=2026-09-10 — прочитаны 4 непривязанных утверждения (разбор ниже), содержательное из них одно
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34499884536
**Commit:** 775122d

## Прогон в чистом клоне

Локальные гейты обходятся (`commit -n`, `STRICT=0`), поэтому доказательством
служит прогон на **склонированном** состоянии, а не в рабочем дереве (§10.4).

```
$ git clone . <clone> && cd <clone> && python3 scripts/delivery_check.py
  ERROR: verify-report.md: Verifier not filled in — Builder must not accept own work (§5.2); write process:ci | agent:NAME | human:NAME
  breakers: kind=bootstrap — объём не мерится (§3.4): развёртывание контура не режется на части, его DoD — §7.3 + приёмка §6
  WARNING: ci-oracles: weak — local gates are bypassable (§10.4); Verifier must attach a clean-clone run to verify-report.md
  delivery_check: 1 error(s), 1 warning(s)
```

Клон содержит механику и не содержит текстов канонов — это и есть проверяемое
поведение варианта D: контур в чужой истории работает, а сам в неё не уезжает.

## Shape oracles
- [x] PASS — `pre-commit run --all-files`: 27 хуков, упавших 0. Проверено и со
      сброшенным окружением (§6): значения путей живут в `entry:`, а не в шелле.
- [x] PASS — гейты видят код: 42, 43, 50 (×8), 52, 54, 73 файла, 12 TS-модулей.
- [x] PASS — `contour_doctor.py`: AUTO 42 · WEAK 10 · ABSENT 0 · DEAD 0 — «лжи нет».

## Behavior oracles
- [x] PASS — `pytest`: 16 тестов (включая цикл миграций в CI, где база одноразовая)
- [x] PASS — `scripts/delivery_check.py`: 0 ошибок, 0 предупреждений
- [x] PASS — `extract_payload.py --check-local .`: см. блок «Вариант D» ниже
- [x] n/a — тестов продукта нет: кода продукта нет. Первые придут в Ф2.

## Product oracles
- [x] n/a — `delivery/evals/smoke` пуст: продукта пока нет
- [x] n/a — `active/eval-smoke.md` не заполняется на классе S (§2.2)

## Вариант D: тексты контура вне git

```
$ python3 extract_payload.py --check-local .
  check-local: отслеживается 0, без игнора 0 — под вариантом D оба числа нулевые
```

## Spec coverage gaps
- Оси ②, ③, ⑤ не развёрнуты — по плану волн, а не по забывчивости. Триггеры и
  предельные сроки: `docs/CONTOUR_ROLLOUT.md`. В STATUS стоят `weak` / `absent`
  с названной причиной.
- `stack-selftest: external` — самопроверка канонов в CI проекта невозможна под
  вариантом D по построению. Гоняется там, где лежат каноны.

## Assertion digest (ревью ожиданий, не кода)

База: `5583fd7` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **18**, из них без ссылки на пример спеки:
**4**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
A4	assert settings.provider == "fixture"
A4	assert settings.api_key == ""
A4	assert settings.history_grouping == "monthly"
A4	assert settings.retry_backoff_sec == (1.0, 5.0, 30.0)
A5	assert "AHREFS_API_KEY" in str(excinfo.value)
A5	assert settings.provider == "live"
-	assert settings.retry_backoff_sec == tuple(values)
-	assert isinstance(settings.retry_backoff_sec, tuple)
-	assert not offenders, "ядро потянуло обвязку:\n" + "\n".join(offenders)
-	assert _imports(tmp) & _FORBIDDEN == {"fastapi", "rq"}
A2	assert response.status_code == 200
A2	assert body["status"] == "ok"
A2	assert body["migration"]
A2	assert body["provider"] == "fixture"
A3	assert response.status_code == 503
A3	assert body["status"] == "unavailable"
A3	assert body["reason"]
A1	assert _enum_types(config.storage.database_url) == []
```

Привязаны к примерам: **A1 A2 A3 A4 A5**. Остальные 4 — нет.

Читать нужно **только строки с `-` в первой колонке**: их ожидание
ничем не подписано. Подпись: `asserts_reviewed_by: human:… at=…`.

asserts_without_example: 4

### Разбор четырёх непривязанных

Ни в одном из них нет ожидаемого значения, придуманного под реализацию:

| Утверждение | Откуда ожидание |
|---|---|
| `settings.retry_backoff_sec == tuple(values)` | Реляционный оракул `parse(format(xs)) == xs` (hypothesis). Значения перебирает раннер — прятать в таком ожидании нечего |
| `isinstance(settings.retry_backoff_sec, tuple)` | То же свойство, вторая половина: тип, а не значение |
| `not offenders` (изоляция ядра) | Раздел **Non-functional** спеки: «ядро не импортирует ни FastAPI, ни RQ». Ожидание подписано, id примера просто нет — правило записано прозой, а не строкой таблицы |
| `_imports(tmp) & _FORBIDDEN == {"fastapi", "rq"}` | Канарейка предыдущего теста: детектор обязан увидеть заведомо запрещённый импорт. Значение задано входом теста двумя строками выше |

Читать здесь нужно одну строку — третью: она проверяет правило спеки, у которого
не было id. В Ф2 такие правила получат id примеров, чтобы дайджест их привязывал.

## Verdict
- [x] READY FOR HANDOFF
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

Поставил Verifier `human:anthony`, 2026-09-10, после чтения отчёта.

Два пункта приняты сознательно, а не проглядены:

- `ci-oracles: tooling`, а не `deployed` — required status checks выключены
  намеренно (работа идёт прямыми пушами в main единственным исполнителем).
  Пересматривается при появлении второго человека.
- `stack-selftest: external` — под вариантом D иначе быть не может: текстов
  канонов в репозитории нет, проверять в CI проекта нечего.

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base 5583fd7 -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 121 code (+5 process docs) / +19483/-52 (net +19431) |
| commits | 7 |
| time_to_accepted_spec | ~0 — spec.md и `human_ok_spec: yes` пришли одним коммитом 5583fd7 (18:14): содержательное согласование шло раньше, в `docs/IMPLEMENTATION_V3.md` и `docs/PHASES_V3.md` |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — .github/workflows/main-guard.yml, .github/workflows/quality.yml, .pre-commit-config.yaml, scripts/lint/adapted.json |
| implement_retries | 3 — возвраты в implement после красных прогонов CI (95892db → 80c5eca → 590f697 → зелёный 775122d). Четыре локальные находки (tasks.md, «Найдено и исправлено по ходу») исправлены внутри первой итерации и возвратом не считаются |
| verify_fails_before_green | 3 — `quality` failure на 95892db, 80c5eca, 590f697; success на 775122d (run 34499884536). Порог §9.2 (≥ 2) сработал, `harness_hardened: yes` — оснастка ужесточена в этой же поставке |
| est_token_or_cost | n/a — расход сессии не измерялся |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.
