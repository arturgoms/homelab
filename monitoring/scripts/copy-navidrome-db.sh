#!/bin/bash
# Copy Navidrome database for Grafana (avoids locking issues)
# Runs via cron every minute

SOURCE="/srv/navidrome/data/navidrome.db"
DEST="/srv/monitoring/grafana/navidrome-readonly.db"

# Use sqlite3 backup command for safe copy (handles WAL mode)
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$SOURCE" ".backup '$DEST'" 2>/dev/null
else
    # Fallback to cp if sqlite3 not available
    cp "$SOURCE" "$DEST" 2>/dev/null
fi

chmod 644 "$DEST" 2>/dev/null
