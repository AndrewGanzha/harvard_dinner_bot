# Backup / Restore Strategy

## MySQL (docker-compose)

Create backup:

```bash
bash scripts/backup_db.sh
```

Restore backup:

```bash
bash scripts/restore_db.sh backups/mysql_YYYYMMDD_HHMMSS.sql
```

## SQLite fallback

If the project runs with `DB_BACKEND=sqlite`, backup can be done by copying the DB file:

```bash
cp app.db backups/app_$(date +%Y%m%d_%H%M%S).db
```

Restore:

```bash
cp backups/app_YYYYMMDD_HHMMSS.db app.db
```
