#!/usr/bin/env bash
# Сообщение в Telegram от скриптов хоста: упавший бэкап, сторож здоровья.
#
#   scripts/notify.sh "текст"
#
# Бот и чат — TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID (окружение или .env, та же
# пара, что у реапера в контейнере). Не заданы — текст уходит в stderr с
# пометкой «НЕ отправлен» и код 0: звавший скрипт свою работу сделал, и
# ненастроенный канал не должен ронять бэкап. Но и молчать нельзя — пометка
# остаётся в журнале крона.
#
# Токен не попадает в командную строку: адрес с ним curl читает из stdin
# (`-K -`). Машина общая, а `ps` показывает аргументы всех процессов.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/host_env.sh
. "$ROOT/scripts/host_env.sh"

text="${1:?укажи текст сообщения}"
token="$(host_env TELEGRAM_BOT_TOKEN)"
chat="$(host_env TELEGRAM_CHAT_ID)"
# Адрес API меняют только тесты: в них вместо Telegram — свой сервер.
api="${TELEGRAM_API_URL:-https://api.telegram.org}"

if [ -z "$token" ] || [ -z "$chat" ]; then
  echo "алерт НЕ отправлен — Telegram не настроен (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID): $text" >&2
  exit 0
fi

if ! curl -sS --fail --max-time 20 --retry 2 -o /dev/null -K - \
  --data-urlencode "chat_id=$chat" --data-urlencode "text=$text" <<CONFIG
url = "$api/bot$token/sendMessage"
CONFIG
then
  echo "алерт НЕ отправлен — Telegram не принял сообщение: $text" >&2
  exit 1
fi
