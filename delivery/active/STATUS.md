# Active delivery status

- **slug:** f1-skeleton
- **stack:** delivery@1.88, cqg@2.32, okf@absent
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes (by=human:anthony, at=2026-09-10) — спека с примерами A1–A5 подписана
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=проект пока ничего не собирает; PDF появится в Ф4
- **ci-oracles:** tooling
  <!-- Гейт мержа в репозитории (`scripts/merge_guard.sh` + pre-push hook + `needs:`
       у downstream-джоб) — работает на любом тарифе. Серверной защиты ветки нет:
       репозиторий публичный, значит правила ветки GitHub доступны бесплатно, но
       включает их человек в UI (CQG §8.5.3). Незакрытый остаток до этого —
       force-push и обход админом; назван в STACK-ACCEPTANCE, а не замолчан. -->
- **worktree:** none reason=единственный исполнитель, main без защиты до В1
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **waivers:** none
- **new_dependency:** fastapi reason=веб-слой по docs/IMPLEMENTATION_V3.md §2 by=agent:claude
- **new_dependency:** sqlalchemy reason=ORM и миграции, требование «хранить сырые данные» by=agent:claude
- **new_dependency:** alembic reason=миграции схемы с первого дня by=agent:claude
- **new_dependency:** asyncpg reason=асинхронный драйвер postgres для SQLAlchemy 2 by=agent:claude
- **new_dependency:** pydantic-settings reason=типизированный конфиг, запрет os.getenv вне config/ by=agent:claude
- **new_dependency:** uvicorn reason=ASGI-сервер для FastAPI by=agent:claude
- **runtime_paths:** none reason=на этой поставке платформенных путей нет; объявляются в Ф2 (живой Ahrefs — сеть и квота) и Ф4 (PDF — системные библиотеки WeasyPrint)
- **model_surface:** n/a reason=в MVP текст кейса шаблонный, модель не вызывается; ось ⑤ придёт волной В3
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **observability:** 1
- **observe_signal:** A1–A5 из spec подтверждены прогоном; `alembic upgrade head` на чистой базе проходит в чистом клоне
- **observe_until:** 2026-09-24
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Волна В1 пройдена

`stack-selftest: external (~/Documents/Prepare)` — вариант D: текстов канонов в
репозитории нет по построению, шаг «Canon payload selftest» в CI невозможен.

Адаптации объявлены в `scripts/lint/adapted.json`: правило `service-no-web`
переписано под раскладку проекта (сервис-слоя `services/` здесь нет — ядро
разложено по темам). С канонным фильтром гейт просматривал 0 файлов, то есть был
зелёным, не просудив ничего.
