#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-file.sql>"
  exit 1
fi

backup_file="$1"
if [[ ! -f "${backup_file}" ]]; then
  echo "File not found: ${backup_file}"
  exit 1
fi

cat "${backup_file}" | docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'

echo "Restore complete from: ${backup_file}"
