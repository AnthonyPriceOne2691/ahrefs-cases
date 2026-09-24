# Verify report: two-campaigns-two-cases

**Date:** 2026-09-24
**Verifier:** human:anthony (приёмка); оракулы и исполнение на копии базы — agent:claude
**asserts_reviewed_by:** n/a (все утверждения ведут к одобренным примерам)
**CI run:** https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36054725420
**Commit:** fffc1cc

## Чем проверено

| Что | Чем | Результат |
|---|---|---|
| W1–W5 до правки | `pytest tests/test_cases_pack.py` на коммите 042ff82 (тесты есть, правки нет), своя копия базы `cases_casepack_tests` | 5 failed по причине дефекта: W1 — в архиве один PDF `two-campaigns.example — Кейс v1.pdf` вместо двух; W2 — у кампании 2026 подсветка «1 000 → 2 000» кампании 2025; W3 — нет файла `… v4.pdf`; W4 — кампания 2026 получила файл кампании 2025; W5 — код возврата 2 (`EmptyArchiveError`: «выжила» запрещённая кампания) в одном прогоне и 0 (запрещённая получила строку `cases` с чужим файлом) в другом |
| W1–W5 после правки | `pytest tests/test_cases_pack.py tests/test_cases_archive.py tests/test_cases_builder.py` | 33 passed |
| Бэкенд целиком | `pytest -q` на своей копии дев-базы (`cases_casepack_tests`) | 714 passed, 3 skipped; на `origin/main` до правки на той же копии — 709 passed, 3 skipped |
| Типы и стиль | `mypy src/ahrefs_cases`, `ruff check`, `ruff format --check` | чисто, 122 файла |
| pre-commit | хуки на коммитах поставки | Passed, `okf-sync` — код и концепт одним коммитом |
| Фазовый гейт | `python3 scripts/delivery_check.py --diff-base origin/main` | 0 ошибок |
| Исполнение на копии дев-базы (W6) | ниже — «Исполнение рисковых путей» | до правки один PDF на две кампании, после — два с разными sha256 |
| CI на ветке поставки, первый прогон | GitHub Actions, PR #27, коммит 10f2587 | tests — fail, 47 failed не по диффу: CI поставил вышедший в тот же час SQLAlchemy 2.1.0, чьё предупреждение об устаревшем `select().distinct(выражение)` (`cache.share_twin_points`) `filterwarnings = error` сделал падением; соседняя ветка четырьмя минутами раньше на 2.0.54 — зелёная. Граница `<2.1` сначала своим коммитом (fffc1cc), затем общей починкой `main` (#28, 2b25a99, Z48) — влита merge-коммитом |
| CI на ветке поставки | GitHub Actions, PR #27, коммит fffc1cc | delivery, gates, tests — pass (715 passed, 2 skipped): https://github.com/AnthonyPriceOne2691/ahrefs-cases/actions/runs/36054725420 |

## Исполнение рисковых путей

`src/ahrefs_cases/cli/case_commands.py` — сборка пачки по настоящей базе.
Исполнено `run_collect.py pack --source fixture` на копии дев-базы
`cases_casepack_check` (75 проектов, 1747 кейсов), переклассифицированной
`run_collect.py classify --source fixture` (good 18, medium 49, poor 4,
insufficient_data 4): у `nordvpn.com` обе кампании средние, у
`zeta-clinic.example` обе средние и под запретом по гео RU. Провайдер
`fixture`, ключа нет, каталог выгрузки — свой в scratchpad; до правки — код
`origin/main` (de97524), после — ветки; перед прогоном «после» копия базы
пересоздана из того же дампа. ZIP распакован, `кейсы.csv` прочитан, sha256 PDF
сверены со строками `case_artifacts`. at=2026-09-24

| Что | До правки | После правки |
|---|---|---|
| отчёт | «кейс собран: 67», «кейсов внутри: 60», «не попал» — 5 строк | «кейс собран: 67», «кейсов внутри: 61», «не попал» — 6 строк |
| PDF в ZIP / различных sha256 / строк `кейсы.csv` | 60 / 60 / 60 | 61 / 61 / 61 |
| `nordvpn.com` в ZIP | `nordvpn.com — Кейс v11.pdf` (sha256 `6d4c7936cbda…`), одна строка списка | `nordvpn.com — Кейс v11.pdf` (`a615f8f0c4e6…`) и `… v11 (2).pdf` (`6d4c7936cbda…`), две строки |
| строки `cases` v11 | 13039 и 13040 — один файл `nordvpn.com — Кейс v11.pdf`, одна sha256 | 13039 — `… v11.pdf`, `a615f8f0c4e6…`; 13040 — `… v11 (2).pdf`, `6d4c7936cbda…`: суммы совпали с файлами архива |
| `zeta-clinic.example` | «не попал zeta-clinic.example» — одна строка на две кампании | две строки |
| вторая сборка подряд | — | 13039 — `… v12.pdf`, 13040 — `… v12 (2).pdf`: «(2)» снова у поздней |

Подсветка у двух строк `nordvpn.com` одинаковая («6 894 → 10 840») и до, и
после: фикстурный ряд строится от конца периода, и у двух кампаний он одной
формы. Различие чисел держит W2 на рядах 1 000 → 2 000 и 3 000 → 3 600.

Следствие для удаления, тоже исполнено на копии (`removal.trace_of` →
`delete_rows` → коммит → `own_files` → `remove_files`, как в
`DELETE /api/projects/{id}`): кампания 13039 после правки уносит свои два PDF,
и свежая пачка запирается до пересборки (`holds_deleted_case`: до — `False`,
после — `True`). До правки первое удаление кампании `nordvpn.com` не стирало
ни одного файла, и пачка отдавалась (поставка удаления, Z39).

После проверки: копии `cases_casepack_check` и `cases_casepack_tests`
удалены, дамп в контейнере удалён, каталоги выгрузки scratchpad стёрты.

## Ревью рисковых мест

**Транзакция БД.** `_pack_and_store` пишет `store_case` и `store_artifact` в
сессии `pack_cases`, а `session.commit()` — один, после упаковки, как было:
`EmptyArchiveError` выходит из функции до записи, и откатывать нечего. Номер
сборки `next_version` читается в той же сессии до рендера, а `store_case`
спрашивает его снова уже после `flush` соседних строк — у двух кампаний разные
`project_id`, поэтому номер одной не сдвигает номер другой (W3: 4 и 1).
`verdicts[one.project_id]` — `KeyError` невозможен: в `wanted` попадает только
попытка, чей `verdict_id` записан в тот же словарь строкой выше.

**Производительность.** Правка не добавляет запросов: `next_version` — по
одному на собранный кейс, как прежде, рендер — один на кейс. `_projects`
сортирует по трём колонкам вместо одной на сотне строк. `.all()` — в тесте
(`_stored` читает строки своего домена).

**Новый модуль** `tests/test_cases_pack.py`: пишет свои строки с коммитом
(`_seed`), берёт свою версию порогов (`isolated_ruleset`) и убирает за собой
(`delete_owned`); каталог выгрузки — `tmp_path` через `config.export.output_dir`.
Проекты стенда в сборке теста дают «вердикта этой версии нет» и в пачку не
попадают.

**Контракт `pack`.** Вход сменился с пар «домен, кейс» на `ToPack` — других
вызывающих, кроме `pack_cases` и тестов архива, нет (`grep pack(`); имена в
архиве (`unique_name`) и состав `кейсы.csv` не менялись, E4–E10 зелёные на
новом входе.

## Чего проверка НЕ доказывает

- **Прод.** На проде сайтов с двумя хорошими кампаниями может не быть; ssh вне
  рамок поставки — это `observe_signal`.
- **Прошлые сборки.** Строки `cases` стенда и прода, уже записанные с чужим
  файлом, не переписываются: у кампании, чьи числа не совпали, свежесть
  (`cases/freshness.py`) скажет «устарел», и следующая сборка даст ей новую
  версию.
- **Какая строка списка — какая кампания.** Строки `кейсы.csv` одного сайта
  различаются файлом и группой, но не периодом — открытый вопрос спеки.

## Spec coverage gaps

- Нет: W1–W5 — тесты, W6 — исполнение выше.

## Verdict
- [x] READY FOR HANDOFF — ждёт подписи human:anthony (verifier)
- [ ] NEED CONVERGE (new tasks)
- [ ] BLOCKED

## Assertion digest (ревью ожиданий, не кода)

База: `origin/main` · сгенерировано `assert_digest.sh`

Новых/изменённых утверждений: **20**, из них без ссылки на пример спеки:
**0**. Вопрос к каждому непривязанному один: **откуда взято ожидаемое
значение — из спеки или придумано под реализацию?**

```
W1	assert _pack() == 0
W1	assert sorted(pdfs) == [
W1	assert len(set(pdfs.values())) == 2, "два разных файла, а не копия одного"
W1	assert sorted((row[1], row[2]) for row in rows) == [
W2	assert sorted(stored) == [2025, 2026], "строка кейса у каждой кампании"
W2	assert stored[2025].shown.startswith("1 000 → 2 000")
W2	assert stored[2026].shown.startswith("3 000 → 3 600")
W2	assert stored[2025].filename != stored[2026].filename
W2	assert pdfs[row.filename] == row.checksum, f"артефакт кампании {year} — её файл в архиве"
W3	assert sorted(pdfs) == [f"{DOMAIN} — Кейс v1.pdf", f"{DOMAIN} — Кейс v4.pdf"]
W3	assert (stored[2025].version, stored[2025].filename) == (4, f"{DOMAIN} — Кейс v4.pdf")
W3	assert (stored[2026].version, stored[2026].filename) == (1, f"{DOMAIN} — Кейс v1.pdf")
W4	assert stored[2025].filename == f"{DOMAIN} — Кейс v{build}.pdf"
W4	assert stored[2026].filename == f"{DOMAIN} — Кейс v{build} (2).pdf"
W5	assert _pack() == EXIT_CONTENT_BLOCKED
W5	assert list(pdfs) == [f"{DOMAIN} — Кейс v1.pdf"]
W5	assert [(row[1], row[2]) for row in rows] == [("good", f"{DOMAIN} — Кейс v1.pdf")]
W5	assert sorted(stored) == [2025], "запрещённая кампания строки кейса не получает"
W5	assert pdfs[stored[2025].filename] == stored[2025].checksum
W5	assert f"не попал {DOMAIN}: контент-запрет: гео: «BY»" in capsys.readouterr().out
```

✅ **Каждое утверждение ведёт к примеру спеки** (W1 W2 W3 W4 W5), а примеры человек
подписал до кода (`human_ok_spec`). Подпись под дайджестом здесь
**не требуется**: она уже стоит, заранее и на числах. Пиши в verify-report
`asserts_reviewed_by: n/a (все утверждения ведут к одобренным примерам)`.

asserts_without_example: 0

## Harness metrics (this shipment)

<!-- generated by scripts/delivery_metrics.py --base origin/main -->

| Metric | Value |
|---|---|
| files_touched / loc_diff | 7 code (+12 process docs) / +446/-47 (net +399) |
| commits | 7 |
| time_to_accepted_spec | 0.0h |
| rework_after_done | 0 (handoff not declared yet) |
| harness_hardened | yes — tests/test_cases_pack.py (новый оракул) |
| implement_retries | 1 — mypy: переменная цикла `item` в `pack` получила два типа (`ToPack` и `PackedCase`), переименована в `wanted` |
| verify_fails_before_green | 1 — первый прогон CI на ветке упал 47 тестами не по диффу (вышел SQLAlchemy 2.1.0, граница `<2.1` — fffc1cc); локально сьют и фазовый гейт зелёные с первого прогона после правки; дайджест первой редакции приписал утверждения W1 находке Z39 из докстроки теста — докстрока поправлена, привязка W1 |
| est_token_or_cost | n/a |

MANUAL-поля заполняет агент/человек на handoff. Если `verify_fails_before_green >= 2` при `harness_hardened: no` — по §9.2 добавь oracle/breaker/hook в этой же поставке.

