"""Настройки экспорта кейсов."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from ahrefs_cases.config._base import Settings


class ExportSettings(Settings):
    """Куда складываем артефакты и в каком формате."""

    output_dir: Path = Field(Path("./data/out"), validation_alias="EXPORT_OUTPUT_DIR")
    default_format: Literal["html", "pdf"] = Field("pdf", validation_alias="EXPORT_FORMAT")
    templates_dir: Path = Field(Path("./templates"), validation_alias="EXPORT_TEMPLATES_DIR")
