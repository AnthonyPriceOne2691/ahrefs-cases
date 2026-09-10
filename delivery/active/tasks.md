# Tasks: contour-wave-0 — развёртывание ① Delivery

Волна В0 по `docs/CONTOUR_ROLLOUT.md`. Порядок осей ① → ② → ③ обязателен;
② и ③ приходят следующими волнами.

- [x] `git init`, публичный ремоут, вариант D выбран и записан
- [x] строки локального игнора в `.git/info/exclude` (каноны + клиентские документы)
- [x] каноны и инструменты самопроверки положены локально
- [x] payload извлечён `extract_payload.py --extract` (76 файлов), взято 28 путей Delivery
- [x] дерево `delivery/` по §2.3: constitution, README, STACK-ACCEPTANCE, active/*, archive/INDEX, evals/smoke
- [x] `delivery/active/.gitkeep` — иначе пустой `active/` исчезнет из git (§2.3a)
- [x] `CONSTITUTION.md` заполнен под продукт: non-negotiables по units, кейсам и контенту
- [x] `.claude/settings.json` из блока `agent-permissions` (§4.5)
- [x] hook A.5 в `AGENTS.md` + правила, специфичные для проекта
- [x] `scripts/delivery_*.py`, `chmod +x`
- [x] `STATUS.md`: `kind: bootstrap`, оси `weak` с названной причиной
- [x] `delivery_check.py` — 0 ошибок (1 warning: ci-oracles weak, ожидаемо до В1)
- [x] `--check-local` — «отслеживается 0, без игнора 0»
- [x] приёмка §6 заполнена, включая разбор «где процедура подвела»
- [x] коммит механики
- [ ] вердикт в `verify-report.md` ставит Verifier (human:anthony) — не Builder (§5.2)
