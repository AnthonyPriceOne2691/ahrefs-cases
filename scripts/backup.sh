#!/usr/bin/env bash
# Бэкап состояния сервиса: база и артефакты кейсов.
#
# Состояние, которое нельзя пересобрать бесплатно, живёт в двух томах:
#   pgdata   — серии метрик, за которые заплачены units Ahrefs, вердикты,
#              версии порогов, журнал расхода и учётные записи;
#   casedata — собранные PDF и ZIP, часть которых уже ушла клиентам агентства.
# Третий том, redisdata, — очередь: она пересобирается запуском прогона и
# намеренно не бэкапится (это проверяет tests/test_backup_covers_state.py).
#
# Ничего, кроме docker compose, не требуется: на сервере агентства не будет ни
# локального pg_dump, ни python-окружения.
#
#   scripts/backup.sh                  # в ./backups, хранить 14 копий
#   BACKUP_DIR=/srv/backups KEEP=30 scripts/backup.sh
#
# Восстановление — scripts/restore.sh. Бэкап, который ни разу не восстанавливали,
# бэкапом не является: проверьте на стенде до того, как он понадобится.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP="${KEEP:-14}"
COMPOSE="${COMPOSE:-docker compose}"
STAMP="$(date +%Y-%m-%d-%H%M)"
TARGET="$BACKUP_DIR/$STAMP"
# Пишем в отдельный каталог и переименовываем в конце: `>` обрезает файл до
# того, как pg_dump скажет хоть слово, и упавший дамп затёр бы предыдущий
# хороший бэкап, снятый в ту же минуту. Ротация тоже видит только готовые копии.
PARTIAL="$TARGET.partial"

cd "$ROOT"

if ! $COMPOSE ps --status running --services 2>/dev/null | grep -qx postgres; then
  # Молчаливый пустой архив хуже отсутствия архива: он выглядит как бэкап и
  # обнаруживается в тот день, когда из него восстанавливают.
  echo "postgres не запущен: бэкап не снят. Подними компоуз или укажи COMPOSE" >&2
  exit 1
fi

rm -rf "$PARTIAL"
mkdir -p "$PARTIAL"
trap 'rm -rf "$PARTIAL"' EXIT

# Архивный формат (-Fc), а не текстовый: восстанавливается выборочно и сжат.
$COMPOSE exec -T postgres pg_dump -U cases -d cases -Fc > "$PARTIAL/cases.dump"

# Артефакты берутся из тома, а не из каталога разработчика: на сервере рядом со
# скриптом лежит только репозиторий, а PDF живут внутри контейнера.
$COMPOSE exec -T api tar -cf - -C /app/data . > "$PARTIAL/casedata.tar"

# Что и чем восстанавливать — рядом с самим бэкапом: через полгода это
# единственное, что будет под рукой.
cat > "$PARTIAL/README.txt" <<INFO
Бэкап Ahrefs Cases от $STAMP
  cases.dump    — pg_dump -Fc базы cases
  casedata.tar  — содержимое /app/data (PDF и ZIP кейсов)
Восстановление: scripts/restore.sh $TARGET --yes
INFO

rm -rf "$TARGET"
mv "$PARTIAL" "$TARGET"
trap - EXIT
echo "снято: $TARGET ($(du -sh "$TARGET" | cut -f1))"

# Ротация по числу копий, а не по возрасту: «хранить 30 дней» на сервере, где
# бэкап месяц не снимался, означает «не хранить ничего».
#
# Цикл через `while read`, а не `mapfile`: последнего нет в bash 3.2, который
# лежит в /bin на macOS. Первый же живой запуск упал на нём — после того, как
# архив был снят: скрипт печатал «снято», возвращал 127 и оставлял ротацию
# несделанной. В cron это выглядело бы как работающий бэкап.
ls -1d "$BACKUP_DIR"/*/ 2>/dev/null | sort -r | tail -n +"$((KEEP + 1))" | while IFS= read -r old; do
  [ -n "$old" ] || continue
  rm -rf "$old"
  echo "удалён старый бэкап: $old"
done
