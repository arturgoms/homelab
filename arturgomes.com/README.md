# arturgomes.com

Personal blog built with [Quartz v4](https://quartz.jzhao.xyz/), deployed on a self-hosted homelab.

## Architecture

```
Obsidian Vault (Mac)
  └── 5. Blog/
        ├── posts/
        ├── projects/
        └── assets/
          │
          │  Syncthing (~10s)
          ▼
Homelab: /srv/syncthing/docs/notes/
          │
          │  inotifywait (blog-watcher container)
          ▼
/srv/arturgomes.com/content/
          │
          │  docker compose up --build (debounced 10s)
          ▼
arturgomes.com (nginx + Quartz static site)
```

## How Publishing Works

The Obsidian vault is the **single source of truth**. The blog repository contains only the Quartz config, watcher service, and Dockerfile — no content.

### Writing a post

1. Create a note in `5. Blog/posts/YYYY/` using the Blog Post template
2. Write with `status: draft` in the frontmatter — nothing deploys
3. Change to `status: published` and save
4. Syncthing syncs the file to the homelab (`/srv/syncthing/docs/notes/`) in ~10 seconds
5. The `blog-watcher` container detects the change via `inotifywait`
6. The watcher copies the file to `content/` and sets a deploy flag
7. After a 10s debounce, `docker compose up --build -d arturgomes` runs (~30–60s)
8. The post is live

### Unpublishing

Change `status: published` back to `status: draft`. The watcher removes the file from `content/` and triggers a rebuild.

### Assets

Non-markdown files (images, SVGs) in `5. Blog/assets/` sync unconditionally — no `status` property needed.

## Services

```yaml
services:
  arturgomes:   # Quartz static site served by nginx
  blog-watcher: # inotifywait daemon that syncs vault → content and triggers rebuilds
```

The `blog-watcher` container:
- Mounts the Syncthing vault as read-only at `/vault`
- Mounts the blog source at `/blog`
- Mounts `/var/run/docker.sock` to trigger rebuilds on the host
- Must use `COMPOSE_PROJECT_NAME=arturgomescom` to match the host project name

## Manual Deploy

```bash
docker compose -p arturgomescom up --build -d arturgomes
```

## Folder Structure (Vault)

```
5. Blog/
├── index.md          → arturgomes.com/
├── about.md          → arturgomes.com/about
├── assets/           → images, SVGs (synced unconditionally)
├── posts/
│   ├── index.md      → arturgomes.com/posts
│   └── YYYY/
│       ├── index.md  → arturgomes.com/posts/YYYY
│       └── my-post.md → arturgomes.com/posts/YYYY/my-post
└── projects/
    ├── index.md      → arturgomes.com/projects
    └── my-project.md → arturgomes.com/projects/my-project
```

## Quartz Config Notes

- `cdnCaching: false` — fonts are downloaded at build time and served locally (eliminates FOUT)
- `fontOrigin: "googleFonts"` — Schibsted Grotesk (headers), Source Sans Pro (body), IBM Plex Mono (code)
- `Plugin.FolderPage({ pageBody: Component.Content() })` — disables auto-generated folder listings; custom `index.md` files are used instead
- `COMPOSE_PROJECT_NAME=arturgomescom` — required in the watcher container so rebuilds target the correct Docker project
