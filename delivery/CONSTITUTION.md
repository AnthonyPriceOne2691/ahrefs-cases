# Delivery constitution

**Version:** 1.0
**Ratified:** 2026-09-10
**Canon stack:** delivery@1.88 · cqg@absent · okf@absent
<!-- cqg/okf придут волнами В1 и В2, см. docs/CONTOUR_ROLLOUT.md -->
**CI:** not-deployed   <!-- §10.4; развернётся волной В1 вместе с CQG -->

## Product non-negotiables

Специфика этого продукта: единственный платный ресурс — units Ahrefs, а выход
уходит клиентам агентства.

- **Ни один запрос к Ahrefs не делается дважды за одни и те же данные.** Закрытый
  месяц истории неизменяем; повторный сбор догружает только новые месяцы.
  Нарушение стоит денег заказчика, а не времени.
- **Прогон не стартует, пока смета не сверена с остатком квоты.** Не смогли
  узнать остаток — не тратим (fail-closed).
- **Числа в кейсе сверяются с данными программно.** Кейс уходит клиенту; цифра,
  которую никто не проверил механикой, — обещание.
- **Стоп-лист контента проверяется перед выдачей артефакта**, а не доверяется
  шаблону.
- **Атрибуция результата — «рост после старта работ»**, никогда «благодаря
  работам». Формулировка юридическая, не стилистическая.
- **Пороги классификации версионируются, вердикт хранит версию.** Иначе прошлые
  решения необъяснимы.
- **Секретов в git нет.** Провайдер Ahrefs по умолчанию `fixture`: разработка идёт
  без ключа, без сети и без расхода квоты.
- **Репозиторий передаётся компании.** Тексты контура в историю не уезжают
  (вариант D, `.git/info/exclude`); механика коммитится.

## Process principles

- Done закрывается **зелёным CI-прогоном** (§10.4), не локальным «у меня прошло».
  Пока CI нет — `ci-oracles: weak`, и это записано, а не подразумевается.
- `STRICT=0` / `git commit -n` — аварийная локальная мера, видимая в PR; в CI запрещены.
1. Spec before broad implementation (class M/L).
2. Vertical slices; no oneshot of the whole plan.
3. Done = oracles (shape + behavior + product), never self-declaration alone.
4. Builder ≠ Verifier.
5. Agent mistake → strengthen harness (oracle / breaker / hook), not only prompts.
6. One `delivery/active` at a time.
7. **Ядро не знает про веб.** Сбор, классификация и сборка кейса — библиотека;
   API, очередь и фронт — обвязка. Проверяется тем, что ядро тестируется без
   сервера и без сети.

## Coding-agent contract (thin ABC)

### Preconditions
- STATUS.md read; class S/M/L known; branch/worktree set.
- Before implement: artifacts per harness §2.2 (S: tasks; M/L: spec+plan+tasks + human_ok_spec).

### Invariants
- No secrets in git; no force-push to main; no done-on-red; no silent scope creep.
- Никакой живой ключ Ahrefs не участвует в тестах: провайдер `fixture`, ответы записанные.

### Governance
- Human OK on spec (M/L). Human OK on plan (L / risky).
- HITL на: переключение провайдера Ahrefs в `live`, первый прогон с расходом units,
  миграции на живой базе, деплой на сервер агентства, выдачу доступов сотрудникам.

### Recovery
- On oracle red: fix ≤ retry budget, else escalate in STATUS.md.

## Agent permissions (§4.5)

Источник истины по **действиям**. Строки ниже обязаны совпадать с
`.claude/settings.json` (`permissions.deny` / `permissions.ask`) — сверяет
`delivery_check` в обе стороны. Правило здесь и не в настройках = запрет,
который не работает; в настройках и не здесь = граница, сдвинутая без ревью.

`allow` тут не перечисляется: это накопительный список конкретных команд,
его место — только в настройках (§4.5, почему).

```text
agent-permissions
# Необратимое: подтверждение здесь не защита, а соучастие.
deny: Bash(git push --force:*)
deny: Bash(git push:* --force-with-lease)
deny: Bash(rm -rf /:*)
deny: Bash(psql:*)
deny: Bash(mysql:*)
deny: Read(./.env)
deny: Read(./**/.env)
# Живой Ahrefs жжёт квоту заказчика: переключение — решение человека, не агента.
deny: Bash(AHREFS_PROVIDER=live:*)
# Обратимо, но платит человек своим временем.
ask: Bash(git push:*)
ask: Bash(gh pr merge:*)
ask: Bash(gh repo edit:*)
ask: Bash(pip install:*)
ask: Bash(npm install:*)
ask: Bash(docker compose up:*)
ask: WebFetch
```

<!-- `gh repo edit` в ask: репозиторий публичный, а в проекте есть локальные
     клиентские документы — смена видимости и настроек проходит через человека. -->

## Pointers to sibling layers (fill if deployed)

- Code shape oracles: `CODE_QUALITY_GATES.md` — [x] not deployed / [ ] deployed  <!-- волна В1 -->
- Domain canon: `OKF_KNOWLEDGE_BUNDLE.md` / `knowledge/` — [x] not deployed / [ ] deployed  <!-- волна В2 -->
- Agent hooks (§10): [x] not deployed / [ ] deployed
- CI oracles (§10.4, workflow per CQG §8): [x] not deployed / [ ] deployed  <!-- волна В1 -->
- Skills catalog: `skills/README.md` — [x] absent / [ ] present

## Project pointers

- Документ реализации: `docs/IMPLEMENTATION_V3.md` (локальный, вне git)
- Фазы Ф1–Ф9: `docs/PHASES_V3.md` (локальный)
- План развёртывания контура волнами: `docs/CONTOUR_ROLLOUT.md` (локальный)
