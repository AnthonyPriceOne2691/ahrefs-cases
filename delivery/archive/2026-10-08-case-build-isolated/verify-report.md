# Verify report: case-build-isolated

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| M91 (repro) | `tests/test_case_isolation.py` (кнопка «Собрать кейсы», очередь `inline`) | **до правки** красный: сборка падала на `VerdictFormatError` целиком, без пачки и судеб; после — два PDF в пачке, у третьего `failed` «не собран: VerdictFormatError: точка вердикта не той формы: 'derived' (первопричина — KeyError: 'derived')», прогон `partial` |
| M92, M93, M95 | `tests/test_case_isolation.py` | до правки красные, после — зелёные; M95 — `show`, `pack`, `render` с упавшей сборкой и `render` с упавшим рисунком: строка «не собран <домен>: …», коды 0, 3, 3, 3 |
| M94 | `tests/test_case_isolation.py` | зелёный и до, и после: сбой базы роняет сборку, как прежде — пример сохраняет поведение и держит мутанта A |
| Мутанты | A — без проброса `SQLAlchemyError`; B — без изоляции рисунка в пачке; C — без судьбы `failed` в `case_fates` | A: M94 красный; B: M92, M93 красные; C: M91, M93 красные (`KeyError` в задаче пачки); код возвращён |
| Полный сьют | `pytest` | 877 passed, 12 skipped — на коде 9f0bf6b; после переноса причины на `failure_reason` и шага M95 с рисунком — тесты кейсов и консоли 42 passed, `test_case_isolation.py` 5 passed; полный сьют с покрытием — CI |
| Слои | `lint-imports` | 2 контракта соблюдены: `cases` и `export` берут `failure_reason` из нижнего слоя `collect` |
| Живой проход | стенд: копия базы `cases_geo`, API и воркер на коде ветки, Chrome по CDP | см. ниже |

## Исполнение рисковых путей

- Сборка пачки кнопкой с упавшим кейсом — на стенде убрал `derived` из точки Б вердикта `bellroy.com`, нажал
  «Пересобрать кейсы» на экране «Кейсы», увидел: прогон №2356 «частично», в строке «62 из 77 · упало 1 ·
  пропущено 14» и «Скачать 62 кейса»; «Что дальше» — «частично. Что не собралось и почему — в журнале ниже.
  Собрано 62 кейса»; в раскрытии — «bellroy.com · упал · не собран: VerdictFormatError: точка вердикта не той
  формы: 'derived' (первопричина — KeyError: 'derived')», контент-запреты — по-прежнему «не отдан»; в пачке дня
  после прогона №2355 — 62 PDF, `bellroy.com` среди них нет. Точку вернул. at=2026-10-08

## Что нашла проверка

- **Строка «не собран» шла мимо перенаправленного вывода:** у `_print_refusals` умолчание `stream=sys.stdout`
  связывалось при импорте модуля, и `capsys` (как и любое перенаправление) её не видел — M95 был красным при
  напечатанной строке. Поток теперь берётся в момент вызова.
- **Своя функция причины повторяла журнал хуже:** `run_journal.failure_reason` уже пишет последнюю ошибку с
  первопричиной и режет строку до 400 знаков — упавший кейс берёт её, а не свою.

## Ревью рисковых мест

**Ошибки.** Изоляция ловит `Exception`, а не `BaseException`: отмена задачи остаётся отменой. Каждый обработчик
оставляет след — `"case_build_failed", extra={"project_id": project.id, "domain": project.domain}` в сборке и
`"case_render_failed",` в пачке и консоли (`logger.exception`, стек целиком), причина уходит в журнал строкой
`outcome, reason = RunItemOutcome.FAILED, f"не собран: {attempt.detail}"`. Консоль не молчит:
`return EXIT_CASE_FAILED if crashed else 0`.

**Транзакция БД.** Сбой базы не изолируется: `except SQLAlchemyError:` пробрасывает его до задачи, и прогон
падает, как прежде (M94), — иначе упавший запрос оставил бы сессию в прерванной транзакции, и следующие
проекты получили бы «не собран» с чужой причиной. Запись кейсов и судеб — прежняя: одна транзакция задачи
(`pack_built` без коммита, `_close_build` и `session.commit()` в `workers/jobs._pack`).

**Безопасность.** Риска нет, потому что новых входов и прав нет: причина видна в журнале прогонов тем же, кто
видел его раньше (`require_right("read")`), а в неё попадает текст исключения сборки или рендера — без ошибок
базы, которые пробрасываются. Длина — не больше 400 знаков (`failure_reason`).

**Производительность.** Риска нет, потому что сборка не делает новых запросов: `try` вокруг прежнего
`_attempt` и прежнего `render_pdf`, судьбы пишутся тем же `add_item`.

## Чего проверка НЕ доказывает

- Прод: живой проект с упавшей сборкой на проде пока не встречался — наблюдение ждёт первого случая; до него
  «Пересобрать кейсы» при передаче команде покажет, что пачка собирается, как прежде.
- Ошибку WeasyPrint настоящую, а не подменённую: M92 и M93 роняют рисунок подменой `render_pdf`.

## Verdict
- [ ] READY FOR HANDOFF — оракулы зелёные; ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **16**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
Z12	assert ruleset_id is not None
M91	assert _fates(card) == {
M91	assert (card["status"], card["projects_failed"], card["error"]) == ("partial", 1, "")
M91	assert _packed(out_dir) == {f"{FIRST} — Кейс v1.pdf", f"{SECOND} — Кейс v1.pdf"}
M92	assert {domain: outcome for domain, (outcome, _) in fates.items()} == {
M92	assert fates[SECOND][1] == "не собран: RuntimeError: рисунок упал на тесте"
M92	assert "контент-запрет: гео: «BY»" in fates[BLOCKED][1]
M92	assert card["status"] == "partial"
M92	assert _packed(out_dir) == {f"{FIRST} — Кейс v1.pdf"}
M93	assert _fates(card) == {
M93	assert (card["status"], card["error"], card["pack"]) == ("partial", "", False)
M93	assert not list(out_dir.glob("*.zip"))
M95	assert (shown, line in capsys.readouterr().out) == (0, True)
M95	assert (packed, line in out, "кейсов внутри: 1" in out) == (3, True, True)
M95	assert (rendered, line in capsys.readouterr().err) == (3, True)
M95	assert (drawn, failed in capsys.readouterr().err) == (3, True)
```

✅ **Каждое утверждение ведёт к примеру спеки** (M91 M92 M93 M95 Z12), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 7 code (+17 process docs) / +526/-42 (net +484) |
| commits | 4 |
| time_to_accepted_spec | n/a (no spec.md in history — class S?) |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_case_isolation.py (новый оракул) |
| implement_retries | MANUAL — fills from session log |
| verify_fails_before_green | MANUAL — count red verify runs (CI run list) |
| est_token_or_cost | MANUAL / n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.

