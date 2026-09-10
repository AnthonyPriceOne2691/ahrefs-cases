# Verify report

**Date:** 2026-09-11
**Verifier:** human:anthony
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам; `assert_digest.sh` — `asserts_without_example: 0`)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/34535275081
**Commit:** 03e2ffb

CI прогонялся на вершине трёх поставок (`d7a3cdd`). Этот коммит проверен
отдельно в чистой проверочной копии: **238 тестов зелёные, 2 skipped**.

## Shape oracles
- [x] PASS — pre-commit, 27 хуков, упавших 0

## Behavior oracles
- [x] PASS — pytest 238 passed, 2 skipped (чистая копия коммита)
- [x] PASS — таблица E1–E13, 16 тестов схемы

## Product oracles
- [x] PASS — числа выбора совпали с расчётом `docs/UNITS_OPTIMIZATION.md` до unit'а
- [x] PASS — golden-таблица классификации не изменилась

## Найдено по ходу
- Дефект перевёрнутого окна (E13): при упоре в глубину истории `date_to`
  оказывался раньше `date_from`. Запрос стоил бы 50 units и выглядел бы как
  «у домена нет истории». Закрыто инвариантом на конструкторе окна.

## Spec coverage gaps
- E9, E11, E14 закрываются третьей поставкой (отчёт и флаг).

## Verdict
- [x] READY FOR HANDOFF
