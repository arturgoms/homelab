#!/usr/bin/env bash
# Blog deploy watcher
# Watches the Obsidian vault blog folder for changes and deploys published posts.
#
# Markdown files: only synced when frontmatter contains `status: published`.
# All other files (images, SVGs, etc.): always synced unconditionally.
# A debounced rebuild is triggered after each batch of changes.
set -euo pipefail

VAULT_BLOG="${VAULT_BLOG:-/vault/5. Blog}"
CONTENT_DIR="${CONTENT_DIR:-/blog/content}"
BLOG_DIR="${BLOG_DIR:-/blog}"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-arturgomescom}"
DEPLOY_FLAG="/tmp/blog-needs-deploy"

log() { echo "[blog-watcher] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

# Returns 0 if the file was changed (synced or removed), 1 if nothing to do
sync_file() {
    local file="$1"
    local rel="${file#"$VAULT_BLOG"/}"
    local dest="$CONTENT_DIR/$rel"

    # Handle deleted files
    if [[ ! -f "$file" ]]; then
        if [[ -f "$dest" ]]; then
            rm -f "$dest"
            log "Removed: $rel"
            return 0
        fi
        return 1
    fi

    # Non-markdown files (images, SVGs, etc.): always sync, no status check
    if [[ "$file" != *.md ]]; then
        mkdir -p "$(dirname "$dest")"
        if ! diff -q "$file" "$dest" > /dev/null 2>&1; then
            cp "$file" "$dest"
            log "Synced asset: $rel"
            return 0
        fi
        return 1
    fi

    # Markdown files: only sync when status: published
    local status
    status=$(sed -n 's/^status:[[:space:]]*//p' "$file" | head -1 | tr -d '[:space:]"'"'" || echo "")

    if [[ "$status" == "published" ]]; then
        mkdir -p "$(dirname "$dest")"
        if ! diff -q "$file" "$dest" > /dev/null 2>&1; then
            cp "$file" "$dest"
            log "Synced: $rel"
            return 0
        fi
    elif [[ -f "$dest" ]]; then
        rm -f "$dest"
        log "Unpublished: $rel"
        return 0
    fi

    return 1
}

deploy() {
    log "Rebuilding blog..."
    docker compose -p "$COMPOSE_PROJECT" -f "$BLOG_DIR/docker-compose.yml" \
        up --build -d arturgomes \
        && log "Deployed successfully." \
        || log "ERROR: Deploy failed — check docker compose logs."
}

# Deploy daemon: waits for the flag, debounces 10s, then deploys
deploy_daemon() {
    while true; do
        if [[ -f "$DEPLOY_FLAG" ]]; then
            sleep 10
            if [[ -f "$DEPLOY_FLAG" ]]; then
                rm -f "$DEPLOY_FLAG"
                deploy
            fi
        fi
        sleep 2
    done
}

# Initial sync on startup
log "Starting — performing initial sync of published posts and assets..."
CHANGED=0
while IFS= read -r -d '' f; do
    sync_file "$f" && CHANGED=1 || true
done < <(find "$VAULT_BLOG" -type f -print0)

if [[ $CHANGED -eq 1 ]]; then
    log "Changes found — queuing initial deploy."
    touch "$DEPLOY_FLAG"
else
    log "Content already up to date."
fi

# Start deploy daemon in background
deploy_daemon &

log "Watching $VAULT_BLOG for changes..."

# File watcher loop — watches all files, not just .md
inotifywait -m -r \
    -e close_write \
    -e moved_to \
    -e delete \
    --format '%w%f' \
    "$VAULT_BLOG" 2>/dev/null | \
while IFS= read -r file; do
    sync_file "$file" && touch "$DEPLOY_FLAG" || true
done
