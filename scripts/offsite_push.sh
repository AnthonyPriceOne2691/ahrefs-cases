#!/usr/bin/env bash
# Внешняя копия бэкапа: зашифровать и положить в S3-совместимое хранилище —
# Cloudflare R2, Backblaze B2 или любое другое с подписью AWS SigV4.
#
#   scripts/offsite_push.sh /srv/backups/ahrefs-cases/2026-09-28-0330
#
# Зовёт её scripts/backup.sh после локальной копии; руками — чтобы отправить
# уже снятую. Локальные копии лежат на том же диске, что и сервис: от ошибки
# человека и порчи базы спасают, от потери машины — нет (docs/PROD.md).
#
# Наружу уходит каталог бэкапа одним tar, зашифрованным gpg (AES-256, пароль
# OFFSITE_PASSPHRASE). В копии — база с учётками и данными клиентов агентства,
# поэтому хранилищу она отдаётся только шифрованной: утёкший ключ бакета без
# пароля ничего не открывает. Пароль — у владельца в менеджере паролей: без
# него внешняя копия бесполезна.
#
# Целостность: SHA-256 тела идёт в подписанном заголовке x-amz-content-sha256,
# и хранилище само отказывает, если принятое тело с ним не совпало.
#
# Настройки (окружение или .env): OFFSITE_S3_ENDPOINT, OFFSITE_S3_REGION,
# OFFSITE_S3_BUCKET, OFFSITE_S3_ACCESS_KEY_ID, OFFSITE_S3_SECRET_ACCESS_KEY,
# OFFSITE_PASSPHRASE; необязательная OFFSITE_PREFIX (по умолчанию ahrefs-cases/).
# Не задано ни одной — копия не настроена: сказать и выйти нулём. Задана часть —
# ошибка с именами недостающих: полунастроенная копия хуже ненастроенной, она
# выглядит работающей.
#
# Ключу бакета хватает права на запись: старые копии удаляет правило жизненного
# цикла бакета, а не этот скрипт, и взломанный сервер не сотрёт внешние копии.
#
# Удалось — отметка .offsite-last рядом с каталогами бэкапов (время и имя
# объекта): по ней сторож здоровья видит, что внешняя копия свежая.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/host_env.sh
. "$ROOT/scripts/host_env.sh"

SOURCE="${1:?укажи каталог бэкапа: scripts/offsite_push.sh <каталог>}"
if [ ! -f "$SOURCE/cases.dump" ]; then
  echo "в $SOURCE нет cases.dump — это не каталог бэкапа" >&2
  exit 2
fi
SOURCE="$(cd "$SOURCE" && pwd)"

REQUIRED="OFFSITE_S3_ENDPOINT OFFSITE_S3_REGION OFFSITE_S3_BUCKET OFFSITE_S3_ACCESS_KEY_ID OFFSITE_S3_SECRET_ACCESS_KEY OFFSITE_PASSPHRASE"
missing=""
given=0
for name in $REQUIRED; do
  value="$(host_env "$name")"
  if [ -n "$value" ]; then
    given=$((given + 1))
    printf -v "$name" '%s' "$value"
  else
    missing="$missing $name"
  fi
done
if [ "$given" -eq 0 ]; then
  echo "внешняя копия не настроена (OFFSITE_*) — есть только локальная"
  exit 0
fi
if [ -n "$missing" ]; then
  echo "внешняя копия настроена не до конца, не заданы:$missing" >&2
  exit 2
fi
PREFIX="$(host_env OFFSITE_PREFIX)"
PREFIX="${PREFIX:-ahrefs-cases/}"

NAME="$(basename "$SOURCE").tar.gpg"
KEY="$PREFIX$NAME"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Шифруется поток: открытого tar на диске не бывает. Пароль идёт через
# дескриптор 3, а не аргументом; `--no-symkey-cache` не даёт агенту gpg
# запомнить его — иначе следующая расшифровка прошла бы без пароля.
tar -C "$(dirname "$SOURCE")" -cf - "$(basename "$SOURCE")" |
  gpg --batch --yes --quiet --pinentry-mode loopback --no-symkey-cache \
    --passphrase-fd 3 --symmetric --cipher-algo AES256 \
    --output "$WORK/$NAME" 3<<<"$OFFSITE_PASSPHRASE"

if command -v sha256sum >/dev/null 2>&1; then
  SUM="$(sha256sum "$WORK/$NAME" | cut -d' ' -f1)"
else
  SUM="$(shasum -a 256 "$WORK/$NAME" | cut -d' ' -f1)"
fi

# Ключ и секрет — в конфиге curl из stdin, а не в аргументах: `ps` на общей
# машине показывает аргументы всех процессов.
if ! curl -sS --fail-with-body --max-time 600 --retry 3 \
  --aws-sigv4 "aws:amz:$OFFSITE_S3_REGION:s3" -H "x-amz-content-sha256: $SUM" \
  -T "$WORK/$NAME" -o "$WORK/answer" -K - \
  "${OFFSITE_S3_ENDPOINT%/}/$OFFSITE_S3_BUCKET/$KEY" <<CONFIG
user = "$OFFSITE_S3_ACCESS_KEY_ID:$OFFSITE_S3_SECRET_ACCESS_KEY"
CONFIG
then
  echo "внешняя копия НЕ отправлена: $KEY — ответ хранилища: $(head -c 400 "$WORK/answer" 2>/dev/null)" >&2
  exit 1
fi

printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$KEY" >"$(dirname "$SOURCE")/.offsite-last"
echo "внешняя копия: $KEY ($(du -h "$WORK/$NAME" | cut -f1), sha256 ${SUM:0:12}…)"
