"""Спеки history-endpoint'ов Ahrefs — различия в данных, а не в коде.

Не реализовано (Ф1). Шесть endpoint'ов отличаются только именем, набором `select`
и ключом списка в ответе; общий транспорт — `ahrefs_transport.py`.

    metrics-history            -> date, org_traffic, org_cost
    keywords-history           -> date, top3, top4_10, top11_20, top21_50, top51_plus
    refdomains-history         -> date, refdomains
    domain-rating-history      -> date, domain_rating
    pages-history              -> date, pages
    total-search-volume-history-> date, search_volume

Параметры и стоимость — docs/RESEARCH_AHREFS_API.md.
`select` просим минимальный: каждое лишнее поле в metrics-history = +10 units.

"""
