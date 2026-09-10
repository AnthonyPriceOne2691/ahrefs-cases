"""Один запрос к Ahrefs site-explorer endpoint'у и его ответ.

Не реализовано (Ф1). Контракт: авторизация Bearer, timeout, классификация статуса
(ok / retry / fatal), exp-backoff (1/5/30s), разбор cost-headers:

    x-api-units-cost-total-actual  — фактически списано
    x-api-units-cost-total         — оценка до отправки
    x-api-units-cost-row           — стоимость строки

Фактические units логируются с первого запроса: расчёты по докам расходятся с
реальностью, а объяснять счёт придётся.
"""
