#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/config.yml"

# Parse --skip flags
SKIP_STEPS=()
for arg in "$@"; do
  case "$arg" in
    --skip=*) SKIP_STEPS+=("${arg#--skip=}") ;;
    --only=*) ONLY_STEP="${arg#--only=}" ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --skip=<step>   Skip a step (can be used multiple times)"
      echo "  --only=<step>   Run only this step"
      echo ""
      echo "Steps: db, sync, rotate, volumes"
      echo ""
      echo "Examples:"
      echo "  $0 --skip=sync          # Skip the rsync step"
      echo "  $0 --skip=db --skip=sync # Skip DB dumps and rsync"
      echo "  $0 --only=volumes       # Only export Docker volumes"
      exit 0
      ;;
  esac
done

should_run() {
  local step="$1"
  if [ -n "${ONLY_STEP:-}" ]; then
    [ "$ONLY_STEP" = "$step" ]
  else
    for s in "${SKIP_STEPS[@]+"${SKIP_STEPS[@]}"}"; do
      [ "$s" = "$step" ] && return 1
    done
    return 0
  fi
}

# Detect interactive terminal before exec redirects stdout
INTERACTIVE=false
[ -t 1 ] && INTERACTIVE=true

# Read config
SOURCE_DIR=$(yq '.source_dir' "$CONFIG")
BACKUP_DEST=$(yq '.backup_dest' "$CONFIG")
RETENTION_DAYS=$(yq '.retention_days' "$CONFIG")

DAY_OF_WEEK=$(date +%w)
DAY_DIR="$BACKUP_DEST/dumps/day-$DAY_OF_WEEK"
LOG_FILE="$BACKUP_DEST/logs/backup-$(date +%Y%m%d-%H%M%S).log"

# Ensure directories exist
mkdir -p "$BACKUP_DEST"/{latest,logs} "$DAY_DIR"

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== Backup started at $(date) ==="
echo "Config: $CONFIG"
echo "Day of week: $DAY_OF_WEEK"

# --- 1. Database dumps ---
if should_run db; then
echo "[1/4] Dumping databases..."

DB_COUNT=$(yq '.databases | length' "$CONFIG")
for i in $(seq 0 $((DB_COUNT - 1))); do
  DB_NAME=$(yq ".databases[$i].name" "$CONFIG")
  DB_CONTAINER=$(yq ".databases[$i].container" "$CONFIG")
  DB_FORMAT=$(yq ".databases[$i].format" "$CONFIG")
  DB_DUMP_DIR=$(yq ".databases[$i].dump_dir" "$CONFIG")
  DB_DUMP_CMD=$(yq ".databases[$i].dump_cmd" "$CONFIG")

  mkdir -p "$DB_DUMP_DIR"
  echo "  $DB_NAME..."

  case "$DB_FORMAT" in
    sql)
      docker exec "$DB_CONTAINER" sh -c "$DB_DUMP_CMD" \
        > "$DB_DUMP_DIR/all-databases.sql" 2>&1 \
        || echo "  WARNING: $DB_NAME dump failed"
      ;;
    dir)
      docker exec "$DB_CONTAINER" sh -c "$DB_DUMP_CMD" 2>&1 \
        && { rm -rf "$DB_DUMP_DIR/data"; docker cp "$DB_CONTAINER:/tmp/backup" "$DB_DUMP_DIR/data"; } \
        || echo "  WARNING: $DB_NAME dump failed"
      ;;
  esac
done
else echo "[1/4] Skipping DB dumps"; fi

# --- 2. Rsync source to latest/ ---
if should_run sync; then
echo "[2/4] Syncing $SOURCE_DIR to latest/..."

EXCLUDES=""
EXCLUDE_COUNT=$(yq '.rsync_excludes | length' "$CONFIG")
for i in $(seq 0 $((EXCLUDE_COUNT - 1))); do
  PATTERN=$(yq ".rsync_excludes[$i]" "$CONFIG")
  EXCLUDES="$EXCLUDES --exclude=$PATTERN"
done

# Show progress when running interactively, quiet when via systemd
PROGRESS_FLAG=""
if [ "$INTERACTIVE" = true ]; then
  PROGRESS_FLAG="--info=progress2"
fi

# Exit code 23 = partial transfer (vanished files) - normal for hot backups
# Exit code 24 = vanished source files - also normal
rsync -a --delete --no-specials --no-devices \
  $PROGRESS_FLAG $EXCLUDES \
  "$SOURCE_DIR/" "$BACKUP_DEST/latest/" || {
  RC=$?
  if [ $RC -eq 23 ] || [ $RC -eq 24 ]; then
    echo "  WARNING: rsync completed with minor issues (code $RC) - some files vanished or sockets skipped"
  else
    echo "  ERROR: rsync failed with code $RC"
    exit $RC
  fi
}
else echo "[2/4] Skipping rsync"; fi

# --- 3. Copy DB dumps to day-of-week folder ---
if should_run rotate; then
echo "[3/4] Rotating DB dumps to day-$DAY_OF_WEEK..."
rm -rf "$DAY_DIR"
mkdir -p "$DAY_DIR"/{db-dumps,volumes}

for i in $(seq 0 $((DB_COUNT - 1))); do
  DB_NAME=$(yq ".databases[$i].name" "$CONFIG")
  DB_FORMAT=$(yq ".databases[$i].format" "$CONFIG")
  DB_DUMP_DIR=$(yq ".databases[$i].dump_dir" "$CONFIG")
  case "$DB_FORMAT" in
    sql) cp "$DB_DUMP_DIR/all-databases.sql" "$DAY_DIR/db-dumps/$DB_NAME-all.sql" 2>/dev/null || true ;;
    dir) cp -r "$DB_DUMP_DIR/data" "$DAY_DIR/db-dumps/$DB_NAME" 2>/dev/null || true ;;
  esac
done


# Clean up local dumps after rotation
echo "  Cleaning up local dumps..."
for i in $(seq 0 $((DB_COUNT - 1))); do
  DB_DUMP_DIR=$(yq ".databases[$i].dump_dir" "$CONFIG")
  rm -rf "$DB_DUMP_DIR"
done
else echo "[3/4] Skipping dump rotation"; fi

# --- 4. Export Docker volumes to day-of-week folder ---
if should_run volumes; then
echo "[4/4] Exporting Docker volumes to day-$DAY_OF_WEEK..."

VOL_COUNT=$(yq '.docker_volumes | length' "$CONFIG")
for i in $(seq 0 $((VOL_COUNT - 1))); do
  VOL=$(yq ".docker_volumes[$i]" "$CONFIG")
  echo "  $VOL..."
  docker run --rm \
    -v "$VOL:/data:ro" \
    -v "$DAY_DIR/volumes:/backup" \
    alpine tar czf "/backup/$VOL.tar.gz" -C /data . 2>/dev/null \
    || echo "  WARNING: Volume $VOL not found or empty"
done
else echo "[4/4] Skipping volume export"; fi

# --- Cleanup old logs ---
find "$BACKUP_DEST/logs" -name "backup-*.log" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null

echo "=== Backup completed at $(date) ==="
