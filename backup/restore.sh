#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/config.yml"

SOURCE_DIR=$(yq '.source_dir' "$CONFIG")
BACKUP_DEST=$(yq '.backup_dest' "$CONFIG")

usage() {
  echo "Usage:"
  echo "  $0 files <service>         - Restore service files from latest/"
  echo "  $0 db <name> <day>         - Restore database dump from day (0-6)"
  echo "  $0 volume <volume> <day>   - Restore Docker volume from day (0-6)"
  echo "  $0 list [day]              - List available backups"
  exit 1
}

[ $# -lt 1 ] && usage

case "$1" in
  files)
    [ $# -lt 2 ] && usage
    SERVICE="$2"
    echo "Restoring $SOURCE_DIR/$SERVICE from latest backup..."
    echo "WARNING: This will overwrite $SOURCE_DIR/$SERVICE with the backup."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0
    rsync -a "$BACKUP_DEST/latest/$SERVICE/" "$SOURCE_DIR/$SERVICE/"
    echo "Done. Restart the service: cd $SOURCE_DIR/$SERVICE && docker-compose up -d"
    ;;
  db)
    [ $# -lt 3 ] && usage
    DB_NAME="$2"
    DAY="$3"
    DUMP_FILE="$BACKUP_DEST/dumps/day-$DAY/db-dumps/$DB_NAME-all.sql"
    [ ! -f "$DUMP_FILE" ] && echo "Dump not found: $DUMP_FILE" && exit 1

    # Find DB config from config.yml
    DB_COUNT=$(yq '.databases | length' "$CONFIG")
    DB_CONTAINER=""
    DB_RESTORE_CMD=""
    for i in $(seq 0 $((DB_COUNT - 1))); do
      NAME=$(yq ".databases[$i].name" "$CONFIG")
      if [ "$NAME" = "$DB_NAME" ]; then
        DB_CONTAINER=$(yq ".databases[$i].container" "$CONFIG")
        DB_RESTORE_CMD=$(yq ".databases[$i].restore_cmd" "$CONFIG")
        break
      fi
    done

    [ -z "$DB_CONTAINER" ] && echo "Database '$DB_NAME' not found in config" && exit 1

    echo "Restoring $DB_NAME from day-$DAY..."
    echo "File: $DUMP_FILE"
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0

    docker exec -i "$DB_CONTAINER" sh -c "$DB_RESTORE_CMD" < "$DUMP_FILE"
    echo "Done."
    ;;
  volume)
    [ $# -lt 3 ] && usage
    VOL="$2"
    DAY="$3"
    TAR="$BACKUP_DEST/dumps/day-$DAY/volumes/$VOL.tar.gz"
    [ ! -f "$TAR" ] && echo "Backup not found: $TAR" && exit 1
    echo "Restoring volume $VOL from day-$DAY..."
    read -p "Continue? [y/N] " confirm
    [ "$confirm" = "y" ] || exit 0
    docker run --rm -v "$VOL:/data" -v "$BACKUP_DEST/dumps/day-$DAY/volumes:/backup" \
      alpine sh -c "rm -rf /data/* && tar xzf /backup/$VOL.tar.gz -C /data"
    echo "Done."
    ;;
  list)
    echo "=== Latest mirror ==="
    ls "$BACKUP_DEST/latest/" 2>/dev/null || echo "  No backup yet"
    echo ""
    if [ $# -ge 2 ]; then
      echo "=== Day $2 dumps ==="
      ls -lR "$BACKUP_DEST/dumps/day-$2/" 2>/dev/null || echo "  No backup for day $2"
    else
      echo "=== Available day dumps ==="
      for d in 0 1 2 3 4 5 6; do
        if [ -d "$BACKUP_DEST/dumps/day-$d" ]; then
          SIZE=$(du -sh "$BACKUP_DEST/dumps/day-$d" 2>/dev/null | cut -f1)
          echo "  day-$d: $SIZE"
        fi
      done
    fi
    ;;
  *) usage ;;
esac
