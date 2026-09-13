#!/usr/bin/env bash
# Восстановление из бэкапа. Операция необратимая: затирает базу и артефакты.
#
#   scripts/restore.sh backups/2026-09-13-0300          # покажет, что сделает
#   scripts/restore.sh backups/2026-09-13-0300 --yes    # выполнит
#
# Подтверждение обязательно и вторым аргументом, а не вопросом в терминале:
# восстановление запускают в плохой день и часто по ssh из скрипта, где
# интерактивного ответа никто не даст, а «Enter на всякий случай» нажимают.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="${COMPOSE:-docker compose}"
SOURCE="${1:-}"
CONFIRM="${2:-}"

if [ -z "$SOURCE" ]; then
  echo "укажи каталог бэкапа: scripts/restore.sh backups/<дата> [--yes]" >&2
  exit 2
fi
if [ ! -f "$SOURCE/cases.dump" ]; then
  echo "в $SOURCE нет cases.dump — это не каталог бэкапа" >&2
  exit 2
fi

cd "$ROOT"

if [ "$CONFIRM" != "--yes" ]; then
  echo "Будет выполнено (сейчас — ничего):"
  echo "  1. остановлены api и worker"
  echo "  2. база cases ОЧИЩЕНА и восстановлена из $SOURCE/cases.dump"
  echo "  3. артефакты кейсов заменены на $SOURCE/casedata.tar"
  echo "  4. api и worker запущены"
  echo "Повтори с --yes, если это то, что нужно."
  exit 0
fi

# Сначала остановить тех, кто пишет: восстановление под работающим воркером
# даёт базу, в которой половина строк из бэкапа, половина из прогона.
$COMPOSE stop api worker

# `--clean --if-exists` вместо пересоздания базы: пересоздание требует прав,
# которых у пользователя приложения может не быть, и рвёт подключения соседей.
$COMPOSE exec -T postgres pg_restore -U cases -d cases --clean --if-exists < "$SOURCE/cases.dump"

if [ -f "$SOURCE/casedata.tar" ]; then
  $COMPOSE run --rm -T --entrypoint sh api -c 'rm -rf /app/data/* && tar -xf - -C /app/data' \
    < "$SOURCE/casedata.tar"
fi

$COMPOSE start api worker
echo "восстановлено из $SOURCE"
echo "проверь: экран прогонов показывает прежние прогоны, экран кейсов — прежние PDF"
