# Active delivery status

- **slug:** thresholds-preview
- **stack:** delivery@1.88, cqg@2.32, okf@0.2
- **stack-selftest:** external (~/Documents/Prepare) — вариант D; постоянное объявление в `delivery/STACK-ACCEPTANCE.md`
- **class:** M
- **kind:** feature
- **repro_test:** n/a reason=не bugfix
- **diagnosis:** n/a reason=не bugfix
- **phase:** handoff
- **builder:** agent:claude
- **verifier:** human:anthony
- **human_ok_spec:** yes at=2026-09-11 by=human:anthony («пороги» — вторая половина того же экрана, порядок согласован)
- **human_ok_plan:** n/a reason=класс M
- **shape-oracles:** cqg-deployed
- **behavior-oracles:** tests-present
- **artifact_oracle:** n/a reason=артефактов не производит
- **ci-oracles:** tooling
- **worktree:** none reason=единственный исполнитель, прямые коммиты в main
- **hooks:** claude (права из delivery/CONSTITUTION.md в .claude/settings.json)
- **blockers:** none
- **new_dependency:** no
- **runtime_paths:** web/src/pages/thresholds/PreviewPanel.tsx reason=предпросмотр считает по всей базе, и как читается его ответ на настоящих данных, видно только исполнением
- **model_surface:** n/a reason=модель не вызывается
- **rule_enforcers:** n/a reason=model_surface не объявлена
- **canon_drift_waiver:** no
- **baseline_growth_waiver:** no
- **waivers:** none
- **observability:** 1
- **observe_signal:** до всякой правки видно, кого версия переложит по группам и кого посчитать нечем
- **observe_until:** 2026-09-26
- **circuit_breakers:** defaults from AGENT_DELIVERY_HARNESS.md §3.4

## Что решает эта поставка

Вторая половина экрана порогов: список версий и ответ на вопрос «что будет,
если считать по этой версии». На калибровке этот вопрос задают десятки раз
подряд и обсуждают втроём — сейчас его можно задать только курлом.

Ответ важен не только тем, кто сменит группу: у предпросмотра четыре исхода, и
три из них легко слить в одно успокаивающее «ничего не изменится».
