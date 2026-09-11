# Active delivery status

- **slug:** ci-editable-root
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** S
- **kind:** bugfix
- **repro_test:** n/a reason=дефект в конфигурации CI; воспроизводится прогоном workflow, в аннотациях каждого прогона висит предупреждение
- **diagnosis:** delivery/active/diagnosis.md
- **phase:** implement
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** n/a reason=класс S
- **human_ok_plan:** n/a reason=класс S
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** ci-run reason=проверяется прогоном CI: аннотация либо есть, либо нет
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** .github/workflows/quality.yml reason=шаг установки проверяется только исполнением в CI; локально его нет вовсе
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** в аннотациях прогона CI нет предупреждений, которые нельзя погасить работой
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Каждый прогон CI печатает предупреждение «editable-установка backend не удалась
— mypy может не видеть рантайм-зависимости проекта». Погасить его в этом
репозитории нельзя ничем: каталога `backend/` здесь нет и не будет — пакет
лежит в корне (`src/ahrefs_cases`, `pyproject.toml` в корне).

Предупреждение, которое висит всегда, перестают читать. А это тот самый канал,
которым шаг установки сообщает о настоящей беде — mypy без рантайм-зависимостей
проверяет меньше, чем кажется.
