"""Пороги классификации: типизированная модель поверх `Ruleset.payload`.

Рабочие пороги живут **в базе**, версиями, и правятся людьми без деплоя — это
требование ТЗ, а не удобство: пороги калибруются итерациями по 10 доменов с
экспертной оценкой, и каждая правка должна оставлять прошлые вердикты
объяснимыми. `config/thresholds.example.yml` — сид первого запуска и справочник
по структуре; правка файла на живом сервисе ничего не меняет.

Разбор строгий и с внятной ошибкой. Пороги приходят из базы, куда их пишет
человек через интерфейс (Ф6): опечатка в структуре обязана падать при чтении с
указанием места, а не превращаться в `None` внутри сравнения, где она станет
тихо неверной группой.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ahrefs_cases import config


class ThresholdsError(ValueError):
    """Пороги нельзя применить: структура не та.

    Отдельный тип, потому что реакция на него особая — не «проект не
    классифицирован», а «классифицировать нельзя ничем»: считать по дефолтам
    значило бы вынести вердикты по порогам, которых никто не утверждал.
    """


class _Model(BaseModel):
    """База: лишние ключи запрещены.

    `extra="forbid"` осознанно, в отличие от конфига приложения. В `.env` живут
    переменные всех доменов, а здесь — один документ, который человек правит
    руками: опечатка `growth_pct_mim` при `extra="ignore"` дала бы порог по
    умолчанию и молча сдвинула границу группы.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Windows(_Model):
    """Окна усреднения точек А и Б."""

    point_a_months: int = Field(2, ge=1, le=12)
    point_b_months: int = Field(2, ge=1, le=12)
    baseline: str = "period"
    pre_start_baseline_months: int = Field(0, ge=0, le=12)
    """Опция ТЗ «показать, что рост начался после старта работ». По умолчанию 0
    (выключено); сам расчёт baseline — Ф3б."""


class Eligibility(_Model):
    """Когда классифицировать нельзя вовсе."""

    min_months_after_start: int = Field(3, ge=1, le=36)
    max_series_gap_months: int = Field(2, ge=0, le=24)
    min_traffic_point_b: float = Field(0, ge=0)
    """Страховка от «+400 % на сайте с 40 визитами». Не из ТЗ, по умолчанию 0."""


class TrafficRule(_Model):
    """Условие по главной метрике — органическому трафику."""

    growth_pct_min: float
    growth_abs_min: float | None = None
    growth_pct_max: float | None = None
    or_high_pct_low_abs: bool = False
    """Вилка «средних» из Приложения А: сюда же попадает проект с ростом
    ≥ 50 %, но абсолютным приростом меньше порога «хороших»."""


class Supporting(_Model):
    """Подтверждающие метрики: ссылочное и позиции."""

    refdomains_growth_pct_min: float
    kw_top10_growth_pct_min: float


class GroupRule(_Model):
    """Правило одной группы целиком."""

    org_traffic: TrafficRule
    supporting_required: int = Field(1, ge=0, le=2)
    supporting: Supporting
    min_months_after_start: int = Field(3, ge=1, le=36)


class Duration(_Model):
    normalize_after_months: int = Field(0, ge=0, le=60)
    """Нормализация на длительность работ — Ф3б, и она ждёт формулу заказчика.
    Здесь поле разбирается, но не применяется: разбирать чужой документ и
    молчать о неизвестных полях — разные вещи."""


class Guards(_Model):
    end_vs_peak_min_pct: float = Field(0, ge=0, le=100)


class ScoreWeights(_Model):
    org_traffic_growth_pct: float = 0.4
    org_traffic_growth_abs: float = 0.3
    kw_top3_growth_abs: float = 0.2
    refdomains_growth_pct: float = 0.1


class Score(_Model):
    weights: ScoreWeights = Field(default_factory=ScoreWeights)


class Thresholds(_Model):
    """Полный набор порогов одной версии."""

    version: str
    windows: Windows = Field(default_factory=Windows)
    eligibility: Eligibility = Field(default_factory=Eligibility)
    groups: dict[str, GroupRule]
    duration: Duration = Field(default_factory=Duration)
    guards: Guards = Field(default_factory=Guards)
    score: Score = Field(default_factory=Score)

    @property
    def good(self) -> GroupRule:
        return self._group("good")

    @property
    def medium(self) -> GroupRule:
        return self._group("medium")

    def _group(self, name: str) -> GroupRule:
        rule = self.groups.get(name)
        if rule is None:
            message = f"в порогах версии {self.version} нет группы {name!r}"
            raise ThresholdsError(message)
        return rule


def parse(payload: dict[str, Any]) -> Thresholds:
    """`Ruleset.payload` → пороги. Ошибка структуры называет поле."""
    try:
        return Thresholds.model_validate(payload)
    except ValidationError as exc:
        message = f"пороги нельзя применить: {exc.error_count()} ошибок структуры\n{exc}"
        raise ThresholdsError(message) from exc


def load_seed(path: Path | None = None) -> Thresholds:
    """Прочитать сид из файла. Используется **только** при первом наполнении базы."""
    source = path or config.classify.thresholds_seed_path
    if not source.exists():
        message = f"сид порогов не найден: {source}"
        raise ThresholdsError(message)
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        message = f"{source}: ожидался словарь порогов"
        raise ThresholdsError(message)
    return parse(raw)
