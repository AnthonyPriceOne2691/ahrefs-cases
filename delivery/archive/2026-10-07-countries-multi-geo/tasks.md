# Tasks: countries-multi-geo

Спека — `spec.md` (примеры M1–M10), план и уроки — `plan.md`.

- [x] Справочник `storage/countries.py` и формат `storage/geo.py` — M1–M5, M10.
- [x] Колонка `projects.geo` шире, миграция `b9c0d1e2f3a4` с откатом — M9.
- [x] Приём: `parse_geo` в `intake/validate.py`, отказ называет код — M2–M4.
- [x] Сбор: страна запроса — первая, весь мир — без параметра — M2, M3.
- [x] Кейс: `geo_label`, текст называет страну цифр, запрет по каждой стране,
      шапка листа — M6, M7.
- [x] API: `geo_label`; подсказка к файлу — M8. Экран — поставка `countries-on-screen`.
- [x] Концепты `intake`, `case-content`, `collection-scheme`; Z53 в реестре.
- [x] verify: pytest целиком (784 passed, 11 skipped), гейты, `delivery_check`, живой проход по стенду; CI — по PR.
