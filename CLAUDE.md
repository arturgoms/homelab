# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a self-hosted homelab infrastructure managing containerized services via Docker Compose. All services are deployed under `/srv/<service-name>/` with their own `docker-compose.yml` files.

## Architecture

**Reverse Proxy:** Traefik handles all HTTP/HTTPS traffic with automatic Let's Encrypt certificates via Cloudflare DNS challenge. Services are exposed through `*.arturgomes.com` subdomains.

**Security:** CrowdSec provides threat detection and blocking at the Traefik layer. IP whitelisting and basic auth protect sensitive dashboards.

**Networking:** All externally-accessible services connect to the shared `exposed` Docker network. Traefik discovers services via Docker labels.

## Common Commands

```bash
# Start a service
cd /srv/<service> && docker-compose up -d

# Stop a service
cd /srv/<service> && docker-compose down

# View logs
docker-compose -f /srv/<service>/docker-compose.yml logs -f

# Restart a service
docker-compose -f /srv/<service>/docker-compose.yml restart

# Pull latest images and recreate
cd /srv/<service> && docker-compose pull && docker-compose up -d
```

## Adding a New Service to Traefik

Services require these Docker labels to be accessible via reverse proxy:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.<name>.entrypoints=http"
  - "traefik.http.routers.<name>.rule=Host(`<subdomain>.arturgomes.com`)"
  - "traefik.http.middlewares.<name>-https-redirect.redirectscheme.scheme=https"
  - "traefik.http.routers.<name>.middlewares=<name>-https-redirect"
  - "traefik.http.routers.<name>-secure.entrypoints=https"
  - "traefik.http.routers.<name>-secure.rule=Host(`<subdomain>.arturgomes.com`)"
  - "traefik.http.routers.<name>-secure.tls=true"
  - "traefik.http.routers.<name>-secure.service=<name>"
  - "traefik.http.services.<name>.loadbalancer.server.port=<port>"
  - "traefik.docker.network=exposed"
networks:
  - exposed
```

## Service Categories

| Category | Services |
|----------|----------|
| Infrastructure | traefik, crowdsec, cloudflare, portainer |
| Storage | nextcloud, immich, syncthing, qbittorrent |
| Automation | n8n, home-assistant |
| Monitoring | monitoring (grafana/prometheus/loki), uptime-kuma, glances |
| AI/ML | stable-diffusion, whisper, openwebui |
| Databases | databases (postgres/pgadmin), mariadb |
| Other | dashy, searxng, wallo, corecontrol, garmin-fetch-data |

## Key Files

- `/srv/traefik/traefik.yml` - Main Traefik config (entrypoints, providers, ACME)
- `/srv/traefik/config.yml` - Static routes for non-Docker services (Proxmox, TrueNAS, Pi-hole, Home Assistant)
- `/srv/<service>/.env` - Environment variables with secrets (databases, n8n, immich, garmin-fetch-data)

## Conventions

- **Network:** Services use the external `exposed` network for Traefik access
- **Restart policy:** `unless-stopped`
- **Timezone:** `America/Sao_Paulo`
- **User/Group:** UID/GID 1000:1000 for most services
- **GPU services:** Use NVIDIA runtime with `deploy.resources.reservations.devices`
- **Data persistence:** `/srv/<service>/data/` or `/srv/<service>/config/`
