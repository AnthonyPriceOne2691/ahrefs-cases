"""Хранилище: проекты, серии метрик, прогоны, вердикты, кейсы.

Ф1 — SQLite; Postgres + Alembic — Ф5. Темы модулей:
- `models.py`     — сущности (см. docs/DOMAIN_MODEL.md)
- `repository.py` — доступ к данным; upsert серий по (project, metric, date, source)
- `schema.py`     — DDL/инициализация до появления миграций
"""
