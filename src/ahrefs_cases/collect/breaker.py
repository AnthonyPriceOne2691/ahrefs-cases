"""Предохранитель на серию неудач: когда Ahrefs лёг, прогон надо остановить.

Требование §5 документа реализации («circuit breaker на серию ошибок»), до сих
пор не реализованное нигде. Смысл денежный: если десять запросов подряд ушли в
таймаут, оставшиеся девяносто уйдут туда же — и каждый будет стоить units,
ничего не принеся.

Считаются неудачи **подряд**, а не всего. Одиночные ошибки — норма: домен со
странным ответом, разовый 500. Серия означает, что дело не в домене.

В CRM агентства тот же класс защиты сделан богаче — доля упавших частей и доля
429 за час, с оговоркой «статистика на двух-трёх наблюдениях слишком шумная».
Здесь взят самый простой вариант, которого хватает при сотне задач в прогоне;
если он окажется груб, порог заменяется долей без правки вызывающих.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ConsecutiveFailureBreaker:
    """Считает неудачи подряд и говорит, пора ли останавливаться."""

    limit: int
    failures: int = field(default=0, init=False)
    tripped_at: int | None = field(default=None, init=False)
    """Номер задачи, на которой сработал предохранитель — попадает в причину,
    чтобы оператор видел, где прогон оборвался, а не только что оборвался."""

    _seen: int = field(default=0, init=False)

    def record(self, *, ok: bool) -> None:
        """Отметить исход задачи."""
        self._seen += 1
        if ok:
            self.failures = 0
            return
        self.failures += 1
        if self.failures >= self.limit and self.tripped_at is None:
            self.tripped_at = self._seen

    @property
    def tripped(self) -> bool:
        return self.tripped_at is not None

    def reason(self) -> str:
        """Причина для `RunItem.reason` — текст читает оператор, не разработчик."""
        return (
            f"прогон остановлен предохранителем: {self.limit} неудач подряд "
            f"(на задаче {self.tripped_at}). Запрос по этому домену не делался — "
            "проверьте доступность Ahrefs и запустите прогон заново, "
            "уже собранное сохранено."
        )
