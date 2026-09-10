"""Выбор провайдера Ahrefs по конфигу.

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
from ahrefs_cases.collect.single_flight import SingleFlightProvider


def build_provider() -> AhrefsProvider:
    """Провайдер, объявленный конфигом, обёрнутый склейкой одинаковых запросов.

    Обёртка ставится здесь, а не в исполнителе: дедупликация — свойство доступа
    к Ahrefs, а не прогона. Прогон, собранный вручную из `AhrefsFixture` (так
    делают тесты), склейки не получает — и это правильно, там проверяют другое.
    """
    inner: AhrefsProvider = AhrefsLive() if config.ahrefs.provider == "live" else AhrefsFixture()
    return SingleFlightProvider(inner)
