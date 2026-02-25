# Blog Publishing Workflow

The source of truth for all blog content is the **Obsidian vault**, not this repository.
Posts are written in Obsidian, synced to the homelab via Syncthing, and automatically
deployed when marked as published.

## How It Works

```
Obsidian Vault (5. Blog/)
        │
        │  Syncthing (automatic, ~10s delay)
        ▼
/srv/syncthing/docs/notes/5. Blog/
        │
        │  blog-watcher container (inotifywait)
        ▼
/srv/arturgomes.com/content/      ← only published files land here
        │
        │  docker compose up --build -d arturgomes (10s debounce)
        ▼
arturgomes.com  (live)
```

## Writing a Post

1. Create a new note inside `5. Blog/posts/` or `5. Blog/projects/` in Obsidian.
2. Add the required frontmatter:

```yaml
---
title: "Your Post Title"
description: "A short description for SEO and previews"
date: 2026-02-24
status: draft          # keep as draft while writing
tags:
  - area/blog          # required — marks note as blog content in the vault
  - topic/homelab      # add relevant vault topic tags
  - docker             # add readable tags for blog display
---
```

3. Write freely. The post will **not** be deployed while `status: draft`.
4. When ready to publish, change `status: draft` to `status: published` and save.
5. Syncthing syncs the file to the homelab (~10 seconds).
6. The watcher detects the change, copies the file to `content/`, and rebuilds the blog (~30-60 seconds).

## Unpublishing

Set `status` back to `draft` (or remove the property). The watcher will remove the file
from `content/` and rebuild.

## Vault Folder Structure

```
5. Blog/
├── index.md            → arturgomes.com/
├── about.md            → arturgomes.com/about
├── posts/
│   ├── index.md        → arturgomes.com/posts
│   └── my-post.md      → arturgomes.com/posts/my-post
└── projects/
    ├── index.md        → arturgomes.com/projects
    └── my-project.md  → arturgomes.com/projects/my-project
```

The folder structure inside `5. Blog/` maps directly to the URL structure.

## Frontmatter Reference

| Property      | Required | Values              | Purpose                                |
|---------------|----------|---------------------|----------------------------------------|
| `title`       | Yes      | string              | Page title and SEO                     |
| `description` | No       | string              | SEO meta description                   |
| `date`        | No       | YYYY-MM-DD          | Publication date shown on post         |
| `status`      | Yes      | `draft`/`published` | Deploy trigger                         |
| `tags`        | No       | list                | Must include `area/blog` for vault nav |

## Services

### blog-watcher container

- **Image**: built from `./watcher/Dockerfile`
- **Base**: `docker:cli` (Alpine) + `bash` + `inotify-tools`
- **Watches**: `/vault/5. Blog/` (read-only mount of Syncthing vault)
- **Writes to**: `/blog/content/` (the blog's Quartz content directory)
- **Triggers**: `docker compose up --build -d arturgomes` via Docker socket
- **Debounce**: 10 seconds — batches rapid saves into a single deploy
- **On startup**: performs a full sync of all published posts

### arturgomes container

- **Image**: built from `./Dockerfile`
- **Stack**: Node 22 → `npx quartz build` → nginx:alpine
- **Rebuild time**: ~30-60 seconds (npm ci is cached via Docker layers)

## Deploying from Scratch

```bash
# On the homelab
cd /srv/arturgomes.com
docker compose up --build -d
```

The watcher will start, do an initial sync of all published vault posts, and deploy.

## Troubleshooting

**Post not appearing after publish:**
```bash
docker logs blog-watcher --tail 50
```

**Force a full re-sync and rebuild:**
```bash
docker restart blog-watcher
```

**Check what's currently in content:**
```bash
ls /srv/arturgomes.com/content/posts/
```
