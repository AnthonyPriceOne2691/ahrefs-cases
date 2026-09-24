# Прод: где живёт сервис и как с ним обращаться

Инструкция для того, кто обслуживает сервис, — в первую очередь для агента,
которому поручили «накати», «посмотри логи», «заведи человека». Что делает
сервис и как им пользоваться — `docs/OPERATIONS.md`; какая машина нужна —
`docs/DEPLOY_REQUIREMENTS.md`.

> **Репозиторий публичный.** Сюда не пишутся ни IP сервера, ни имя сайта (в
> имени вида `*.sslip.io` зашит IP), ни пароли, ни значения из `.env`. Ниже
> вместо них — команды, которые достают их с машины.

## Коротко

| Что | Где |
|---|---|
| Вход на машину | `ssh prod-hetzner` — алиас в `~/.ssh/config` на Mac владельца, ключ там же. Пароль в ssh выключен, только ключи |
| Адрес машины | `ssh -G prod-hetzner \| grep '^hostname'` |
| Имя сайта | `ssh prod-hetzner grep -m1 server_name /etc/nginx/sites-available/ahrefs-cases` |
| Каталог сервиса | `/srv/ahrefs-cases` — клон этого репозитория, ветка `main` |
| Настройки и секреты | `/srv/ahrefs-cases/.env`, `chmod 600`, только на сервере |
| Порт сервиса | `127.0.0.1:8091` — только петля; наружу 80/443 держит nginx хоста |
| Сайт nginx хоста | `/etc/nginx/sites-available/ahrefs-cases` (из `deploy/proxy/ahrefs-cases.conf`) |
| Пароль прокси | `/etc/nginx/ahrefs-cases.htpasswd` |
| Бэкапы | `/srv/backups/ahrefs-cases`, крон `/etc/cron.d/ahrefs-cases` |
| Пароли, выданные при установке | `/root/ahrefs-cases.credentials` (`chmod 600`) — читает человек, в чат не выводить |

**Агент ходит на прод только с разрешения человека.** Авто-режим Claude Code
по умолчанию отклоняет ssh на боевую машину, даже на чтение, и это правильно:
разрешение даёт владелец, а не соседняя сессия и не сам агент. На машине
владельца оно выдано правилом `Bash(ssh prod-hetzner:*)` в
`.claude/settings.local.json` проекта (файл вне git). Добавляет его человек:
правку собственных прав классификатор агенту не даёт. Правило — префикс,
поэтому команды пишутся ровно `ssh prod-hetzner '...'`, без ключей перед
именем.

**Сценарий длиннее одной строки — файлом, а не через stdin.** Вариант
`ssh prod-hetzner 'bash -s' < сценарий` не работает: первый же
`docker compose exec` внутри съедает остаток stdin, и сценарий обрывается
молча. Кладут файлом (`ssh prod-hetzner 'cat > /root/x.sh' < x.sh`) и
запускают с `< /dev/null`.

## Машина общая

На сервере живут и другие сервисы; каждый — в своём `/srv/<сервис>/`, со своим
портом на петле и своим файлом в `/etc/nginx/sites-available/`. Отсюда правила:

- **Чужое не трогать:** каталоги `/srv/<другой сервис>/`, их файлы nginx и
  htpasswd, их контейнеры и порты. Список соседей — `ls /srv`,
  `ls /etc/nginx/sites-enabled`.
- **Настройки машины не трогать:** ssh (пароль выключен нарочно — его
  перебирали тысячами попыток в сутки), ufw (открыты 22/80/443), fail2ban.
- **`docker compose` — только из `/srv/ahrefs-cases`.** Никаких
  `docker system prune`, `docker volume prune`, `docker stop $(docker ps -q)`:
  они бьют по соседям.
- **`nginx -t` перед каждым `reload`.** Файлы всех сайтов включаются в один
  блок `http`: ошибка в нашем файле роняет перезагрузку для всей машины. По той
  же причине имена зоны и формата журнала у нас с префиксом `cases_`.
- **certbot — только со своим именем** (`-d <имя сайта>`): без `-d` он
  предложит перевыпустить сертификаты соседей.
- **`00-deny` — общий файл машины**, а не чей-то сайт: `default_server` на 80
  отвечает 444, на 443 рвёт рукопожатие (`ssl_reject_handshake on`). Без него
  https с чужим именем или по голому IP попадал бы в первый по алфавиту сайт —
  после нашей выкладки это были бы мы. Правится с копией и `nginx -t`, и о
  правке говорят соседям.

## Обновить

```bash
ssh prod-hetzner
cd /srv/ahrefs-cases
BACKUP_DIR=/srv/backups/ahrefs-cases scripts/backup.sh   # перед обновлением — всегда
git pull --ff-only
docker compose build
docker compose up -d        # migrate отработает раньше api: так устроен depends_on
docker compose ps           # api healthy, worker и web Up, migrate Exited (0)
curl -s http://127.0.0.1:8091/api/health   # status ok; migration — голова alembic
```

Простой — время пересборки, минуты. Сборка идёт на самой машине: ресурсов на
ней с большим запасом.

**Откат.** `git checkout <прежний коммит>`, `docker compose build`,
`docker compose up -d`. Если обновление несло миграцию, откат кода схему назад
не вернёт — тогда восстановление из бэкапа, снятого перед обновлением (ниже).

## Настройки: `.env` сервера

Файл свой у сервера и в git не едет. Состав (значения — только на машине):

| Переменная | Что | Заметка |
|---|---|---|
| `POSTGRES_PASSWORD` | пароль базы | **только hex** (`openssl rand -hex 24`): он вставляется в DSN, и `@/:` его ломают. Правкой файла не меняется — база помнит пароль с первого запуска |
| `JWT_SECRET` | подпись токенов входа | `openssl rand -hex 32`. Смена разлогинивает всех |
| `WEB_PORT` | `8091` | порт на петле; `WEB_BIND` по умолчанию `127.0.0.1` |
| `LOG_FORMAT` | `json` | поля `run_id` и прочие из `extra` видны в логах |
| `AHREFS_PROVIDER` | `fixture` | `live` — **только решением владельца**: живой ключ жжёт units |
| `AHREFS_API_KEY` | ключ Ahrefs | кладёт владелец или по его слову; в чат и логи не выводить |

Всё из `.env` доезжает до `migrate`, `api` и `worker` целиком (`env_file`), так
что любая ручка из `.env.example` работает и на сервере. Проверять поведением,
а не чтением файла: `docker compose config | grep -c LOG_FORMAT` — ненулевое
число значит «доехало». ⚠ На машине с настоящим ключом `docker compose config`
печатает значения — смотреть только `grep` по имени, не весь вывод.

После правки `.env` — `docker compose up -d`: компоуз сам пересоздаст
контейнеры, у которых изменилось окружение. Переменные через оболочку
(`AHREFS_PROVIDER=... docker compose up -d worker`) не передавать: следующая
команда без них молча вернёт прежнее (урок L197).

## Воронка из консоли

С 24.09.2026 (B6) воронку проходят кнопками: «Запустить прогон» — шаг 1 и
группы, «Дособрать кандидатов» — шаг 2 и данные под кейс, «Собрать кейсы» —
PDF и пачка. Те же ступени из консоли — для инженера, когда нужно сузить
список (`--only`) или разобраться:

```bash
cd /srv/ahrefs-cases
docker compose exec api python scripts/run_collect.py classify    # бесплатно
docker compose exec api python scripts/run_collect.py stage2      # платно: кандидаты
docker compose exec api python scripts/run_collect.py case-data   # платно: good/medium
```

В `fixture` всё бесплатно; перед переключением в `live` — раздел 1
`docs/FINDINGS.md`.

## Логи

```bash
cd /srv/ahrefs-cases
docker compose logs -f --tail=200 api worker        # JSON по строке
docker compose logs worker | grep '"run_id": "<id>"' # один прогон целиком
tail -f /var/log/nginx/ahrefs-cases.access.log       # прокси: путь без параметров, код, время
```

Ошибки nginx — в общем `/var/log/nginx/error.log` машины.

## Люди

Логин — почта вида `имя@parsingprices.com`. Домен ничей, писем на логины
сервис не шлёт, адрес — просто уникальное имя.

```bash
cd /srv/ahrefs-cases
docker compose exec api python scripts/run_collect.py useradd имя@parsingprices.com user
```

Пароль команда спросит дважды; пустой ввод — сгенерировать, покажет один раз.
Группы: `user` — прогоны и чтение, `admin` — плюс пороги и люди, `engineer` —
плюс технические настройки. Дальше людьми управляют на экране «Люди» (право
`manage_users`).

**Пароль прокси** — второй замок перед экраном входа, один на всех:

```bash
htpasswd /etc/nginx/ahrefs-cases.htpasswd cases     # сменить пароль
htpasswd /etc/nginx/ahrefs-cases.htpasswd имя       # завести ещё одного
```

`reload` для htpasswd не нужен: файл читается на каждый запрос.

## Бэкап и восстановление

Крон (`/etc/cron.d/ahrefs-cases`) каждую ночь снимает `scripts/backup.sh` в
`/srv/backups/ahrefs-cases` и хранит 14 копий; журнал —
`/var/log/ahrefs-cases-backup.log`. В копии — дамп базы и артефакты кейсов
(PDF и ZIP); очередь не бэкапится намеренно.

⚠ **Копии лежат на том же диске, что и сервис.** Внешнего хранилища пока нет:
от ошибки человека и от порчи базы бэкап спасает, от потери машины — нет.

```bash
scripts/restore.sh /srv/backups/ahrefs-cases/<дата>         # покажет, что сделает
scripts/restore.sh /srv/backups/ahrefs-cases/<дата> --yes   # затрёт базу и артефакты
```

Восстановление останавливает `api` и `worker`, очищает базу, раскладывает
артефакты и запускает обратно. После — войти и посмотреть экраны прогонов и
кейсов.

## Сайт, сертификат, имя

Шаблон — `deploy/proxy/ahrefs-cases.conf`; на сервере лежит копия с настоящим
именем и строками, которые дописал certbot (`listen 443 ssl`, пути к
сертификату, редирект с http). Правишь шаблон — переноси правку руками, не
затирай серверный файл целиком: пропадут строки certbot.

Что делает сайт: оболочка приложения — за паролем прокси; `/api/` открыт (фронт
ходит с `Authorization: Bearer`, и basic auth на том же заголовке отказал бы
каждому запросу — API защищён входом сервиса); вход ограничен 10 попытками в
минуту на адрес (`limit_req`, всплеск 5, дальше 429); схемы API снаружи нет.

Продление сертификата — системный таймер certbot
(`systemctl list-timers | grep certbot`).

**Смена имени** (появился свой домен): A-запись поддомена на IP машины → в
`/etc/nginx/sites-available/ahrefs-cases` поменять `server_name` → `nginx -t &&
systemctl reload nginx` → `certbot --nginx -d <новое имя> --redirect`.

## Проверка снаружи

После установки и после любой правки сайта — с любой машины, не с сервера:

| Запрос | Ожидаем |
|---|---|
| `curl -sI http://<имя>/` | `301` на https |
| `curl -s -o /dev/null -w '%{http_code}' https://<имя>/` | `401` — пароль прокси |
| то же с `-u cases:<пароль прокси>` | `200` |
| `https://<имя>/api/docs` | `404` — схемы снаружи нет |
| `https://<имя>/api/usage` без входа | `401` |
| 12 неверных `POST /api/auth/login` подряд **с одного адреса** | `401`, потом `429` (с 7-й попытки). С Mac владельца `429` может не появиться вовсе: его выход раскидан по нескольким внешним IP, а лимит — на адрес. Надёжно — с самого сервера на публичное имя |
| `curl --max-time 5 http://<IP>:8091/` | соединение не устанавливается |

## Как ставили с нуля

На случай переезда на другую машину. Порядок важен: сайт nginx ссылается на
файл паролей, а certbot — на работающий сайт.

1. `git clone https://github.com/AnthonyPriceOne2691/ahrefs-cases.git /srv/ahrefs-cases`
2. `.env` из таблицы выше: секреты генерировать **на сервере**, `chmod 600`.
3. `docker compose build && docker compose up -d`; `curl
   http://127.0.0.1:8091/api/health`.
4. Пороги: `docker compose exec api python scripts/run_collect.py classify` —
   Ahrefs не трогает, на пустой базе засевает версию по умолчанию. Без неё
   экран проектов отвечает `503` «нет активной версии порогов». Код выхода 1
   здесь не сбой: проектов ещё нет, «классифицировано 0», а версия записана.
5. Первый человек: `useradd … engineer` (см. «Люди»).
6. Сайт: шаблон с настоящим `server_name` в `sites-available`, ссылка в
   `sites-enabled`, `htpasswd -c /etc/nginx/ahrefs-cases.htpasswd cases`,
   `nginx -t && systemctl reload nginx`, затем `certbot --nginx -d <имя>
   --non-interactive --agree-tos --register-unsafely-without-email --redirect`.
7. Крон бэкапа; первую копию снять руками и **проверить восстановлением**.
8. Проверка снаружи — таблица выше.
