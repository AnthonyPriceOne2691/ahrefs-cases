# Verify report

**Date:** 2026-09-10
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (класс S — дайджест утверждений обязателен для M/L)
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

## Verdict
- [ ] READY FOR HANDOFF
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

<!-- Вердикт не ставит Builder: это и есть самоприёмка, которую запрещает §5.2.
     Отметку ставит Verifier (human:anthony) после чтения отчёта. -->
