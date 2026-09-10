"""Типизированный конфиг — единственный вход к настройкам.

Правило проекта: `os.getenv` / `os.environ` вне этого пакета запрещены, доступ —
только через объекты ниже. `getattr(config, "K", default)` прячет опечатку от
mypy, поэтому тоже запрещён.

Один домен настроек = один файл. Экземпляры создаются один раз при импорте:
конфиг читается на старте, и мисконфиг падает там же, а не в середине платного
прогона (см. `AhrefsSettings._live_needs_key`).
"""

from __future__ import annotations

from ahrefs_cases.config.ahrefs import AhrefsSettings, HistoryGrouping, Provider
from ahrefs_cases.config.auth import AuthSettings
from ahrefs_cases.config.classify import ClassifySettings
from ahrefs_cases.config.export import ExportSettings
from ahrefs_cases.config.storage import StorageSettings

ahrefs = AhrefsSettings()
storage = StorageSettings()
auth = AuthSettings()
classify = ClassifySettings()
export = ExportSettings()

__all__ = [
    "AhrefsSettings",
    "AuthSettings",
    "ClassifySettings",
    "ExportSettings",
    "HistoryGrouping",
    "Provider",
    "StorageSettings",
    "ahrefs",
    "auth",
    "classify",
    "export",
    "storage",
]
