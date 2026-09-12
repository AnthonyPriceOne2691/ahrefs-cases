"""Источник рядов называет вызывающий — умолчания нет ни у кого.

Это оракул против **третьего** повторения урока L53. Дважды до этого выбор
источника подставлялся умолчанием — и оба раза в живом режиме сервис читал
пустоту: preflight сверял смету с фикстурной квотой, карточка проекта рисовала
пустые графики. На третий раз (12.09.2026) живой прогон собрал пять доменов, а
классификация объявила «данных не хватает» по всем.

Общее у трёх случаев одно: на фикстурах умолчание совпадает с истиной, поэтому
**ни один тест поймать это не может** — он и сам идёт на фикстурах. Ловится
только живым режимом или проверкой сигнатуры. Здесь — проверка сигнатуры.
"""

from __future__ import annotations

import inspect

import pytest

from ahrefs_cases.cases.builder import build_cases
from ahrefs_cases.classify.diagnose import diagnose_domain, diagnose_poor
from ahrefs_cases.classify.preview import preview
from ahrefs_cases.classify.recalc import recalc
from ahrefs_cases.classify.verdicts import (
    classify_all,
    classify_project,
    classify_projects,
    compute_verdict,
)

SERIES_READERS = [
    classify_all,
    classify_project,
    classify_projects,
    compute_verdict,
    preview,
    recalc,
    diagnose_poor,
    diagnose_domain,
    build_cases,
]


@pytest.mark.parametrize("reader", SERIES_READERS, ids=lambda f: f.__name__)
def test_source_has_no_default(reader: object) -> None:
    """У `source` нет значения по умолчанию: режим называет вызывающий.

    Умолчание здесь — не удобство, а тихий выбор за пользователя: код,
    написанный и проверенный на фикстурах, в бою продолжает читать фикстуры и
    сообщает «данных нет» вместо ответа.
    """
    parameter = inspect.signature(reader).parameters.get("source")  # type: ignore[arg-type]

    assert parameter is not None, "reader читает ряды — она обязана спрашивать источник"
    assert parameter.default is inspect.Parameter.empty, (
        f"у {reader.__name__} вернулось умолчание источника: "  # type: ignore[attr-defined]
        "на фикстурах оно совпадёт с истиной, в живом режиме — нет"
    )
