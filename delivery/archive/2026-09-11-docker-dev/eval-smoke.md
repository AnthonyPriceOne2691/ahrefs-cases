# Eval smoke — this shipment

Derived from spec acceptance. Run during verify.

- [x] E1 — `up -d` поднимает шесть сервисов
- [x] E2 — `/api/health` отвечает, миграция применена
- [x] E3 — экран входа открывается, вход работает через прокси
- [x] E4 — правка `src/` подхватывается без пересборки
- [x] E5 — правка `web/src/` подхватывается сама
- [x] E6 — контекст сборки без `.venv` и `node_modules`
- [x] E7 — `node_modules` машины не подменяет контейнерные
- [x] E8 — api ждёт готовности базы
