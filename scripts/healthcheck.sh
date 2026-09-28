#!/usr/bin/env bash
# Сторож здоровья хоста: раз в пять минут из крона, алерт в Telegram, когда
# состояние СМЕНИЛОСЬ — беда появилась или прошла. Не каждый тик: алерт,
# повторяющийся каждые пять минут, перестают читать к обеду.
#
#   */5 * * * * root cd /srv/ahrefs-cases && BACKUP_DIR=/srv/backups/ahrefs-cases scripts/healthcheck.sh >> /var/log/ahrefs-cases-health.log 2>&1
#
# Смотрит то, чего изнутри контейнеров не видно:
#   1. контейнеры сервиса запущены и не unhealthy — Docker их по unhealthy не
#      перезапускает нарочно (docs/PROD.md), значит, кто-то должен сказать;
#   2. API отвечает `ok` через web — тот же путь, что у человека;
#   3. ночной бэкап свежий — крон, который не запустился вовсе, backup.sh не
#      поймает: он просто не исполнится;
#   4. внешняя копия свежая, если настроена.
#
# Telegram не принял — состояние не записывается, и алерт повторится в
# следующий тик. Не настроен — notify.sh печатает текст в журнал и выходит
# нулём: состояние записывается, журнал не заваливается повтором.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/host_env.sh
. "$ROOT/scripts/host_env.sh"

COMPOSE="${COMPOSE:-docker compose}"
NOTIFY="${NOTIFY:-$ROOT/scripts/notify.sh}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
STATE_FILE="${STATE_FILE:-/var/lib/ahrefs-cases/health.state}"
MAX_AGE_MIN=$((${BACKUP_MAX_AGE_H:-26} * 60))
SERVICES="postgres redis api worker reaper web"
PORT="$(host_env WEB_PORT)"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT:-8080}/api/health}"

cd "$ROOT"
problems=""
note() { problems="$problems$1"$'\n'; }

# Здоровье пустое у сервиса без healthcheck — это не беда; беда — не running
# (exited, restarting) или unhealthy. `--all`: остановленный тоже в списке.
states="$($COMPOSE ps --all --format '{{.Service}} {{.State}} {{.Health}}' 2>/dev/null || true)"
for service in $SERVICES; do
  row="$(printf '%s\n' "$states" | awk -v s="$service" '$1 == s { print $2, $3; exit }')"
  case "$row" in
    "") note "$service: контейнера нет" ;;
    running\ unhealthy) note "$service: unhealthy" ;;
    running*) ;;
    *) note "$service: ${row% *}" ;;
  esac
done

if ! curl -fsS --max-time 10 "$HEALTH_URL" 2>/dev/null | grep -q '"status" *: *"ok"'; then
  note "API не отвечает ok ($HEALTH_URL)"
fi

newest="$(ls -1d "$BACKUP_DIR"/*/ 2>/dev/null | sort | tail -n 1 || true)"
if [ -z "$newest" ]; then
  note "бэкапов нет в $BACKUP_DIR"
elif [ -n "$(find "$newest" -maxdepth 0 -mmin +"$MAX_AGE_MIN")" ]; then
  note "последний бэкап старше $((MAX_AGE_MIN / 60)) ч: $(basename "$newest")"
fi

if [ -n "$(host_env OFFSITE_S3_BUCKET)" ]; then
  mark="$BACKUP_DIR/.offsite-last"
  if [ ! -f "$mark" ] || [ -n "$(find "$mark" -mmin +"$MAX_AGE_MIN")" ]; then
    note "внешняя копия не отправлялась больше $((MAX_AGE_MIN / 60)) ч"
  fi
fi

now="${problems:-ok}"
now="${now%$'\n'}"
was="$(cat "$STATE_FILE" 2>/dev/null || echo ok)"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $(printf '%s' "$now" | paste -sd ';' -)"
[ "$now" = "$was" ] && exit 0

if [ "$now" = ok ]; then
  text="Ahrefs Cases: снова в порядке (было: $(printf '%s' "$was" | paste -sd ';' -))"
else
  text="Ahrefs Cases: беда — $(printf '%s' "$now" | paste -sd ';' - | sed 's/;/; /g')"
fi
if "$NOTIFY" "$text"; then
  mkdir -p "$(dirname "$STATE_FILE")"
  printf '%s\n' "$now" >"$STATE_FILE"
fi
