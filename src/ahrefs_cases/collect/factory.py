"""Выбор провайдера Ahrefs и источника остатка квоты по конфигу.

Одно место, где решается «фикстуры или живой API». Разбросай это условие по
вызовам — и переключение в live стало бы не решением, а следствием того, какой
модуль первым дошёл до Ahrefs.

Проверку «live без ключа» здесь не дублируем: она стоит в конфиге и падает на
старте процесса (`AhrefsSettings._live_needs_key`), то есть раньше, чем сюда
дойдёт управление.
"""

from __future__ import annotations

from ahrefs_cases import config
from ahrefs_cases.collect.fixtures.provider import AhrefsFixture
from ahrefs_cases.collect.live import AhrefsLive
from ahrefs_cases.collect.provider import AhrefsProvider
from ahrefs_cases.collect.quota import FixtureQuota, LiveQuota, QuotaSource
from ahrefs_cases.collect.single_flight import SingleFlightProvider


def build_provider() -> AhrefsProvider:
    """Провайдер, объявленный конфигом, обёрнутый склейкой одинаковых запросов.

    Обёртка ставится здесь, а не в исполнителе: дедупликация — свойство доступа
    к Ahrefs, а не прогона. Прогон, собранный вручную из `AhrefsFixture` (так
    делают тесты), склейки не получает — и это правильно, там проверяют другое.
    """
    inner: AhrefsProvider = AhrefsLive() if config.ahrefs.provider == "live" else AhrefsFixture()
    return SingleFlightProvider(inner)


def build_quota() -> QuotaSource:
    """Откуда узнавать остаток units — по тому же конфигу, что и провайдер.

    До этой функции источник выбирался **умолчанием вызывающего**: прогон брал
    `FixtureQuota()`, если ему не передали другой, и в живом режиме сверял смету
    с фикстурными десятью тысячами вместо настоящего остатка. Проверка,
    выглядевшая работающей, не защищала ничего — и заметно это стало бы в Ф7,
    на первых настоящих деньгах.
    """
    return LiveQuota() if config.ahrefs.provider == "live" else FixtureQuota()
