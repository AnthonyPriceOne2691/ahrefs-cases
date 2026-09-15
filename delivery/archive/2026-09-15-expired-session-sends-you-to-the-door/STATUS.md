# Active delivery status

- **slug:** expired-session-sends-you-to-the-door
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** web/src/auth/__tests__/session-expiry.test.tsx
- **diagnosis:** n/a reason=причина найдена чтением слоя и записана как Z23: `ApiError.needsLogin` не вызывается ни одним экраном, а проверка «кто я» идёт только на монтировании
- **phase:** accepted
- **builder:** agent:claude
- **verifier:** human:anthony (принято 15.09.2026 — «Принимаю, оставьте», в ответ на прямой вопрос о приёмке)
- **human_ok_spec:** yes at=2026-09-15 by=human:anthony («вот я после ночи открыл ноут и требуется действующий токен, давай поправим этот момент»)
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** n/a reason=правка слоя обращений к API, внешних вызовов не добавляет
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** вкладка, простоявшая ночь, утром показывает форму входа со словами «сессия истекла», а не строку сервера в карточках
- **observe_until:** 2026-09-29
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Z23. Владелец открыл ноутбук утром 15.09.2026: в шапке он числился вошедшим, а
в карточках экранов «Кейсы» и «Загрузка» стояла строка сервера — «нужен
действующий токен».

Две причины, и обе о доверии к обещанию.

**Признак без потребителя.** У `ApiError` с самого начала есть `needsLogin`
(`status === 401`). Его не вызывает **ни один экран**: все рисуют
`error.message`, то есть `detail` с бэкенда. Тот же класс, что Z17 — право,
которого не проверяет ни один роутер.

**Обещание, исполняемое наполовину.** Докстрока `AuthProvider` говорит: «выход
по `401` живёт здесь же». Живёт — но только на монтировании, единственной
проверкой `/api/auth/me` за загрузку страницы. Вкладка, оставленная на ночь,
ловит протухание уже после: «кто я» больше не спрашивают, состояние «вы вошли»
остаётся в памяти, а данные приходят с `401`.

Третьим шло мигание белым: `retry: 1` повторял запрос на `401`, и каждый повтор
снимал карточку и ставил заглушку загрузки заново.
