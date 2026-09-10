# Research: Ahrefs API v3 — что даёт историю по проекту

Проверено по докам Ahrefs (docs.ahrefs.com, сентябрь 2026).
Всё, что помечено «оценка», требует проверки живым ключом.

## Ключевой вывод

Точечные метрики (`metrics`, `domain-rating`, `backlinks-stats`, `refdomains`,
`metrics-by-country`) — хорошо изученная часть API. Историю за период отдаёт
отдельный слой `*-history`, и именно он несёт основную неопределённость по
стоимости и качеству данных.

## Endpoint'ы под нашу задачу

База: `https://api.ahrefs.com/v3/site-explorer/…`, авторизация — `Authorization: Bearer <key>`.

### Динамика за период (ядро кейса)

| Endpoint | Отдаёт | Обязательные параметры |
|---|---|---|
| `GET /metrics-history` | `date, org_traffic, org_cost, paid_traffic, paid_cost` по датам | `target`, `date_from` |
| `GET /keywords-history` | распределение позиций: `top3, top4_10, top11_20, top21_50, top51_plus` по датам | `target`, `date_from` |
| `GET /refdomains-history` | `date, refdomains` | `target`, `date_from` |
| `GET /domain-rating-history` | DR по датам | `target`, `date_from` |
| `GET /pages-history` | число страниц по датам | `target`, `date_from` |
| `GET /total-search-volume-history` | суммарный объём поиска по датам | `target`, `date_from` |

Общие опциональные параметры этих endpoint'ов:

- `date_to` — конец периода (по умолчанию «сегодня»);
- `history_grouping` = `daily` | `weekly` | `monthly` (**default `monthly`**);
- `mode` = `exact` | `prefix` | `domain` | `subdomains` (**default `subdomains`**);
- `protocol` = `both` | `http` | `https` (default `both`);
- `country` — двухбуквенный ISO-код (для гео-разреза);
- `volume_mode` = `monthly` | `average`; `traffic_mode` = `static` | `adaptive` (default `adaptive`);
- `select` — список колонок; `output` = `json` | `csv` | `xml` | `php`.

### Срез «сейчас» и вспомогательное

| Endpoint | Зачем нам |
|---|---|
| `GET /metrics` | сверка финальной точки Б (в CRM уже используется) |
| `GET /metrics-by-country` | гео-разрез трафика, если кейс про конкретный рынок |
| `GET /organic-keywords` | конкретные ключи для «а вот эти запросы выросли» в тексте кейса |
| `GET /top-pages` | какие страницы дали рост — сильный аргумент в кейсе |
| `GET /backlinks-stats`, `GET /refdomains` | ссылочный профиль на конец периода |
| `GET /subscription-info/limits-and-usage` | остаток квоты, **0 units** — используем как preflight |

## Стоимость (units)

Что известно из докладной части доков:

- минимальная стоимость запроса — **50 units**; сверху зависит от числа строк и полей;
- в `metrics-history` каждое из полей `org_traffic`, `org_cost`, `paid_traffic`, `paid_cost` — **10 units**;
- `refdomains-history` — **5 units** за запрос (документировано отдельно);
- `subscription-info/limits-and-usage` — **0 units**.

Ahrefs возвращает фактическую стоимость в заголовках ответа — это надёжнее любых
расчётов по докам, и их надо логировать с первого запроса:

- `x-api-units-cost-total-actual` — фактически списано;
- `x-api-units-cost-total` — оценка до отправки;
- `x-api-units-cost-row` — стоимость строки.

**Оценка (проверить на Ф0):** 4 history-запроса на проект при `monthly` ≈ 150–250 units,
то есть 100 проектов ≈ 15–25k units за прогон. Если реальность окажется в разы
дороже — придётся резать набор метрик (см. вопрос Q7 в OPEN_QUESTIONS).

## Ограничения, которые уже видны

1. **`select` экономит units.** Просить только нужные колонки — не стилистика, а деньги.
2. **`monthly` по умолчанию** — для кейса на 6–12 месяцев этого достаточно; `daily`
   раздувает строки и стоимость. Класть grouping в конфиг.
3. **`mode=subdomains` по умолчанию** — для проекта-домена это обычно верно, но
   для кейса по конкретному разделу нужен `prefix`. Это поле проекта, не глобальный флаг.
4. **Трафик Ahrefs — оценка, не факт.** Кейс, построенный на `org_traffic`, — кейс на
   оценке. Если кейсы уходят клиенту, стоит предусмотреть опциональную сверку с GSC (Q4).
5. **Глубина истории ограничена тем, что хранит Ahrefs** и зависит от тарифа —
   проверить на Ф0 на домене с длинной историей.
6. **Нет endpoint'а «видимость».** «Видимость» придётся собирать самим из
   `keywords-history` (доля top3 / top10) или из `total-search-volume-history` — см. Q3.
7. **Квота общая на workspace и на ключ** (в CRM это два отдельных бакета).
   Прогон по большому списку способен выжечь квоту, которой пользуются другие
   сервисы — отсюда preflight-проверка и мягкий стоп `AHREFS_UNITS_MIN_LEFT`.

## Источники

- [Site Explorer — список endpoint'ов](https://docs.ahrefs.com/api/reference/site-explorer)
- [Metrics history](https://docs.ahrefs.com/en/api/reference/site-explorer/get-metrics-history)
- [Keywords history](https://docs.ahrefs.com/en/api/reference/site-explorer/get-keywords-history)
- [Refdomains history](https://docs.ahrefs.com/en/api/reference/site-explorer/get-refdomains-history)
- [Introduction / units](https://docs.ahrefs.com/en/api/docs/introduction)
