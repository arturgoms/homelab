---
title: Publishing Posts from Obsidian
description: How I made my Obsidian vault the source of truth for my blog, with automatic deploys triggered by a single frontmatter change
date: 2026-02-24
status: published
tags:
  - area/blog
  - topic/homelab
  - topic/note-taking
---

My blog posts used to live in two places at once — a half-finished idea in Obsidian and a polished version in the blog's Git repository. Every time I wanted to update a post, I had to remember which copy was canonical, copy content between apps, and manually SSH into my homelab to trigger a rebuild. It was just enough friction to make me not bother.

The fix turned out to be simpler than I expected: make the vault the only place posts live, and automate everything else.

I use Obsidian as my second brain — notes, meetings, projects, and now blog posts all live in the same vault, organized by a system built around folders as state and tags as context. If you're curious about how the vault itself is structured, I wrote a full breakdown in [[the-obsidian-manual|The Obsidian Manual]].

---

## The Problem

I use [Quartz](https://quartz.jzhao.xyz/) for my blog — a static site generator built specifically for Obsidian vaults. It handles wikilinks, frontmatter, tags, and backlinks natively. My blog *already spoke Obsidian*. But my posts still lived inside the blog's Git repository at `/srv/arturgomes.com/content/`, completely disconnected from my vault.

The result was a slow drift. Notes in Obsidian would get updated and refined. The published version would go stale. I'd occasionally remember to sync them manually, but mostly I just wouldn't.

The vault should be the source of truth. The blog should be a consequence of the vault, not the other way around.

---

## Why Not Obsidian Sync?

The obvious question: Obsidian has a [first-party sync service](https://obsidian.md/sync) ($8–10/month). Why build this at all?

The short answer is that **Obsidian Sync solves a different problem**. It syncs vault content between Obsidian *apps* — your Mac, iPhone, iPad. It's designed to keep the app in sync across your devices, not to expose vault files as regular filesystem paths on a Linux server.

That distinction matters here. The file watcher on the homelab needs to see the vault as actual files on disk — it calls `inotifywait` on a directory and reads the markdown files directly. Obsidian Sync doesn't give you that. It's a closed sync channel between Obsidian clients, not a general-purpose file sync tool.

Syncthing, on the other hand, syncs files as files. The homelab gets a real directory at `/srv/syncthing/docs/notes/` that the watcher can monitor like any other folder on the filesystem.

| | Obsidian Sync | Syncthing |
|---|---|---|
| Cost | $8–10/month | Free |
| Sync target | Obsidian apps only | Any device / filesystem |
| File access on server | No | Yes — regular files on disk |
| Works for this setup | No | Yes |
| Version history | Yes (up to 12 months) | No (needs separate backup) |
| Setup complexity | Zero | Moderate |
| Already in my homelab | No | Yes |

The last row is the practical one — Syncthing was already running in my stack for other purposes. There was no extra cost to using it here.

That said, they're not mutually exclusive. If you pay for Obsidian Sync for multi-device access (phone, tablet, etc.) you can still run Syncthing separately for the homelab deploy pipeline. They operate at different layers.

---

## My Approach

### The Setup

My [[homelab|homelab]] already had most of the pieces in place:

- **Obsidian vault** synced to my homelab via [Syncthing](https://syncthing.net/) — any save on my Mac appears at `/srv/syncthing/docs/notes/` within ~10 seconds
- **Quartz blog** running as a Docker container at `/srv/arturgomes.com/`, served via nginx behind Traefik
- **No CI/CD** — the blog rebuilt by running `docker compose up --build` on the homelab

### The Vault Folder

I added a `5. Blog/` folder to my vault following my existing [[the-obsidian-manual|naming convention]] (numbered folders as namespaces). Everything inside maps directly to a URL:

```
5. Blog/
├── index.md            → arturgomes.com/
├── about.md            → arturgomes.com/about
├── assets/             → images, SVGs — synced unconditionally
│   └── keyboard.jpg
├── posts/
│   └── my-post.md      → arturgomes.com/posts/my-post
└── projects/
    └── my-project.md   → arturgomes.com/projects/my-project
```

### The Deploy Trigger

Rather than deploying on every save (which would rebuild constantly while drafting), I used a frontmatter property as the trigger:

```yaml
---
title: "My Post"
date: 2026-02-24
status: draft       # ← keep here while writing
---
```

Changing `status: draft` to `status: published` is the only action needed to deploy. The file watcher on the homelab handles the rest.

### The Watcher Container

Since I couldn't install packages on the homelab without root, I containerized the watcher. The `Dockerfile` lives at `/srv/arturgomes.com/watcher/Dockerfile`:

```dockerfile
FROM docker:cli

RUN apk add --no-cache bash inotify-tools

COPY watch.sh /usr/local/bin/watch.sh
RUN chmod +x /usr/local/bin/watch.sh

ENTRYPOINT ["/usr/local/bin/watch.sh"]
```

- `docker:cli` — Alpine base with the Docker CLI pre-installed (needed to trigger rebuilds)
- `inotify-tools` — provides `inotifywait` for efficient filesystem event watching (no polling)
- `bash` — required for the watch script

The `watch.sh` script does three things: initial sync on startup, file-level sync on every change, and debounced rebuilds:

```bash
#!/usr/bin/env bash
set -euo pipefail

VAULT_BLOG="${VAULT_BLOG:-/vault/5. Blog}"
CONTENT_DIR="${CONTENT_DIR:-/blog/content}"
BLOG_DIR="${BLOG_DIR:-/blog}"
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-arturgomescom}"
DEPLOY_FLAG="/tmp/blog-needs-deploy"

log() { echo "[blog-watcher] $(date '+%Y-%m-%d %H:%M:%S') $*"; }

sync_file() {
    local file="$1"
    local rel="${file#"$VAULT_BLOG"/}"
    local dest="$CONTENT_DIR/$rel"

    if [[ ! -f "$file" ]]; then
        if [[ -f "$dest" ]]; then
            rm -f "$dest" && log "Removed: $rel" && return 0
        fi
        return 1
    fi

    # Non-markdown files (images, SVGs, etc.): always sync, no status check
    if [[ "$file" != *.md ]]; then
        mkdir -p "$(dirname "$dest")"
        if ! diff -q "$file" "$dest" > /dev/null 2>&1; then
            cp "$file" "$dest" && log "Synced asset: $rel" && return 0
        fi
        return 1
    fi

    # Markdown files: only sync when status: published
    local status
    status=$(sed -n 's/^status:[[:space:]]*//p' "$file" | head -1 | tr -d '[:space:]"'"'" || echo "")

    if [[ "$status" == "published" ]]; then
        mkdir -p "$(dirname "$dest")"
        if ! diff -q "$file" "$dest" > /dev/null 2>&1; then
            cp "$file" "$dest" && log "Synced: $rel" && return 0
        fi
    elif [[ -f "$dest" ]]; then
        rm -f "$dest" && log "Unpublished: $rel" && return 0
    fi

    return 1
}

deploy() {
    log "Rebuilding blog..."
    docker compose -p "$COMPOSE_PROJECT" -f "$BLOG_DIR/docker-compose.yml" \
        up --build -d arturgomes \
        && log "Deployed." || log "ERROR: Deploy failed."
}

deploy_daemon() {
    while true; do
        if [[ -f "$DEPLOY_FLAG" ]]; then
            sleep 10
            if [[ -f "$DEPLOY_FLAG" ]]; then
                rm -f "$DEPLOY_FLAG" && deploy
            fi
        fi
        sleep 2
    done
}

# Initial sync — all files, not just .md
log "Starting — syncing published posts and assets..."
CHANGED=0
while IFS= read -r -d '' f; do
    sync_file "$f" && CHANGED=1 || true
done < <(find "$VAULT_BLOG" -type f -print0)
[[ $CHANGED -eq 1 ]] && touch "$DEPLOY_FLAG" || log "Already up to date."

deploy_daemon &

log "Watching $VAULT_BLOG..."
inotifywait -m -r -e close_write -e moved_to -e delete \
    --format '%w%f' "$VAULT_BLOG" 2>/dev/null | \
while IFS= read -r file; do
    sync_file "$file" && touch "$DEPLOY_FLAG" || true
done
```

The deploy daemon runs as a background process. It watches for a flag file and waits 10 seconds after the last change before rebuilding — so rapid saves while editing don't trigger a rebuild storm.

### Wiring It Into Docker Compose

The watcher runs as a service alongside the blog:

```yaml
services:
  arturgomes:
    build: .
    container_name: arturgomes
    restart: unless-stopped
    # ... traefik labels

  blog-watcher:
    build: ./watcher
    container_name: blog-watcher
    restart: unless-stopped
    volumes:
      - /srv/syncthing/docs/notes:/vault:ro   # vault, read-only
      - /srv/arturgomes.com:/blog              # blog source
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - "VAULT_BLOG=/vault/5. Blog"
      - CONTENT_DIR=/blog/content
      - BLOG_DIR=/blog
      - COMPOSE_PROJECT_NAME=arturgomescom
```

### The Gotcha: Compose Project Name

This tripped me up. When `docker compose up --build` runs *inside* the watcher container, it resolves the project name from the directory of the compose file — which inside the container is `/blog`, giving project name `blog`. But the `arturgomes` container was originally started from `/srv/arturgomes.com/` on the host, so its project name is `arturgomescom`.

Docker Compose saw two different projects and tried to create a new container with the same name, resulting in:

```
Error: Conflict. The container name "/arturgomes" is already in use
```

The fix is explicit: pass `-p arturgomescom` in the deploy command and set `COMPOSE_PROJECT_NAME=arturgomescom` in the watcher's environment so it always matches.

---

## Result

The workflow now is:

1. Create a note in `5. Blog/posts/` using the Blog Post template
2. Write with `status: draft` — nothing deploys
3. Change to `status: published`, save
4. Syncthing syncs the file to the homelab (~10 seconds)
5. The watcher picks it up, copies it to `content/`, and queues a rebuild
6. After the 10s debounce, `docker compose up --build -d` runs (~30-60 seconds)
7. The post is live

To unpublish, change back to `status: draft`. The watcher removes the file from `content/` and rebuilds.

The entire blog — every post, every project page, the home and about pages — now lives in `5. Blog/` inside my Obsidian vault. The blog repository contains only the Quartz config, the watcher service, and the Dockerfile. No content.

---

## Key Takeaways

- Quartz is Obsidian-native, so the migration was mostly just moving files and adding `status: published`
- `inotifywait` is more efficient than polling but needs `inotify-tools` in the container
- Containerizing the watcher keeps the homelab clean and makes the setup fully reproducible
- The `COMPOSE_PROJECT_NAME` env var is essential when triggering Docker rebuilds from inside a container
- A debounce (10s) prevents rebuild storms from rapid saves
- Non-markdown assets (images, SVGs) sync unconditionally — no `status` property needed, just drop them in `5. Blog/assets/`

---

## Updates

- **2026-02-24** — Added asset syncing: non-markdown files (images, SVGs) in `5. Blog/` are now synced unconditionally by the watcher, without requiring `status: published`
- **2026-02-24** — Initial publication
