#!/usr/bin/env bash
set -euo pipefail

mkdir -p backups
timestamp="$(date +%Y%m%d_%H%M%S)"
backup_file="backups/mysql_${timestamp}.sql"

docker compose exec -T mysql sh -c \
  'mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  > "${backup_file}"

echo "Backup created: ${backup_file}"
