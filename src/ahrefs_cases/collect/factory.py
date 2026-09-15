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
    """Откуда узнавать остаток units — по НАЛИЧИЮ КЛЮЧА, а не по режиму рядов.

    До этой функции источник выбирался **умолчанием вызывающего**: прогон брал
    `FixtureQuota()`, если ему не передали другой, и в живом режиме сверял смету
    с фикстурными десятью тысячами вместо настоящего остатка. Проверка,
    выглядевшая работающей, не защищала ничего — и заметно это стало бы в Ф7,
    на первых настоящих деньгах.

    **Решение владельца 15.09.2026: остаток спрашивается у ключа всегда.**
    Прежде он привязывался к `provider`, и на стенде с фикстурными рядами смета
    показывала «Остаток квоты: 10 000» — зашитое учебное число, выданное экраном
    за настоящий остаток ключа (около 1,46 млн). Числа без источника уже стоили
    нам Z10 и Z23; здесь цена выше — по этой строке решают, запускать ли прогон.

    Признак теперь — ключ, а не режим рядов, и это важно для двух случаев:
    запрос остатка **бесплатен** (`subscription-info`, 0 units), а без ключа
    ходить в сеть нельзя вовсе. Ключа нет — остаётся `FixtureQuota`: так живут
    тесты и чистая установка, и мягкий стоп по-прежнему срабатывает в
    разработке, а не впервые на живых деньгах.
    """
    return LiveQuota() if config.ahrefs.api_key else FixtureQuota()
