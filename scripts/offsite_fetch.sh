#!/usr/bin/env bash
# Внешняя копия обратно: список, скачивание и расшифровка — для восстановления,
# в том числе на чистой машине (docs/PROD.md, «Восстановление из внешней копии»).
#
#   scripts/offsite_fetch.sh list                           # что лежит в хранилище
#   scripts/offsite_fetch.sh get latest /srv/restore        # последняя копия
#   scripts/offsite_fetch.sh get 2026-09-28-0330.tar.gpg /srv/restore
#
# `get` кладёт в каталог назначения тот же каталог бэкапа, что снимал
# scripts/backup.sh, и печатает команду восстановления — scripts/restore.sh.
#
# Настройки — те же OFFSITE_*, что у scripts/offsite_push.sh, но ключу бакета
# здесь нужно право ЧТЕНИЯ: серверный ключ только пишет, так взломанный сервер
# не сотрёт копии. Ключ на чтение выпускают в день восстановления и отдают
# окружением, не правя .env (docs/PROD.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/host_env.sh
. "$ROOT/scripts/host_env.sh"

usage() {
  echo "scripts/offsite_fetch.sh list | get <latest|имя.tar.gpg> <каталог>" >&2
  exit 2
}

COMMAND="${1:-}"
case "$COMMAND" in
  list) ;;
  get) [ $# -eq 3 ] || usage ;;
  *) usage ;;
esac

REQUIRED="OFFSITE_S3_ENDPOINT OFFSITE_S3_REGION OFFSITE_S3_BUCKET OFFSITE_S3_ACCESS_KEY_ID OFFSITE_S3_SECRET_ACCESS_KEY"
[ "$COMMAND" = get ] && REQUIRED="$REQUIRED OFFSITE_PASSPHRASE"
missing=""
for name in $REQUIRED; do
  value="$(host_env "$name")"
  if [ -n "$value" ]; then
    printf -v "$name" '%s' "$value"
  else
    missing="$missing $name"
  fi
done
if [ -n "$missing" ]; then
  echo "не заданы:$missing" >&2
  exit 2
fi
PREFIX="$(host_env OFFSITE_PREFIX)"
PREFIX="${PREFIX:-ahrefs-cases/}"
BASE="${OFFSITE_S3_ENDPOINT%/}/$OFFSITE_S3_BUCKET"

# curl с подписью SigV4; ключ и секрет — из stdin, не в аргументах (`ps`).
s3() {
  curl -sS --fail-with-body --max-time 600 --retry 3 \
    --aws-sigv4 "aws:amz:$OFFSITE_S3_REGION:s3" -K - "$@" <<CONFIG
user = "$OFFSITE_S3_ACCESS_KEY_ID:$OFFSITE_S3_SECRET_ACCESS_KEY"
CONFIG
}

# Имена копий, старые первыми. Имя — время снятия, поэтому порядок строк и есть
# порядок времени. Больше тысячи копий (три года ежедневных при выключенной
# очистке) — нужна постраничная выборка; правило жизненного цикла до неё не пускает.
names() {
  # Косая в префиксе кодируется заранее: подпись считается по закодированному
  # запросу, и curl, и хранилище должны видеть одну и ту же строку.
  s3 "$BASE?list-type=2&prefix=${PREFIX//\//%2F}" |
    grep -o '<Key>[^<]*</Key>' | sed -e 's/^<Key>//' -e 's/<\/Key>$//' -e "s|^$PREFIX||" | sort
}

if [ "$COMMAND" = list ]; then
  names
  exit 0
fi

NAME="$2"
DEST="$3"
if [ "$NAME" = latest ]; then
  NAME="$(names | tail -n 1)"
  [ -n "$NAME" ] || { echo "в $BASE/$PREFIX копий нет" >&2; exit 1; }
fi
mkdir -p "$DEST"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

s3 -o "$WORK/$NAME" "$BASE/$PREFIX$NAME"
# Сначала расшифровка целиком, распаковка — потом: gpg сверяет целостность
# только дочитав до конца, и потоком в tar испорченная копия успела бы
# наполовину распаковаться и выглядеть бэкапом.
if ! gpg --batch --quiet --pinentry-mode loopback --no-symkey-cache --passphrase-fd 3 \
  --output "$WORK/backup.tar" --decrypt "$WORK/$NAME" 3<<<"$OFFSITE_PASSPHRASE"; then
  echo "не расшифровано: $NAME — неверный OFFSITE_PASSPHRASE или копия испорчена" >&2
  exit 1
fi
tar -C "$DEST" -xf "$WORK/backup.tar"

STAMP="${NAME%.tar.gpg}"
echo "расшифровано: $DEST/$STAMP"
echo "дальше: scripts/restore.sh $DEST/$STAMP          # покажет, что сделает"
echo "        scripts/restore.sh $DEST/$STAMP --yes    # восстановит"
