---
title: "Homelab"
description: "Self-hosted infrastructure running on Docker with Traefik and Cloudflare Tunnel"
date: 2024-01-01
tags:
  - docker
  - self-hosting
  - infrastructure
  - traefik
  - homelab
---

My self-hosted infrastructure running 20+ services on Docker with Traefik as reverse proxy and Cloudflare Tunnel for secure external access.

## Architecture

```
Internet → Cloudflare Tunnel → Traefik → Docker Services
                                  ↓
                            Let's Encrypt (SSL)
```

## Services

### Applications
- **Immich** - Photo & video management (Google Photos alternative)
- **Nextcloud** - File sync & storage
- **n8n** - Workflow automation
- **Home Assistant** - Home automation
- **SearXNG** - Privacy-focused search engine
- **Open WebUI** - AI chat interface
- **Syncthing** - File synchronization

### AI & Media
- **Whisper** - Speech-to-text transcription
- **Stable Diffusion** - Image generation

### Monitoring & Security
- **CrowdSec** - Intrusion detection & threat intelligence
- **Prometheus + Grafana** - Metrics & dashboards
- **Glances** - System monitoring
- **Umami** - Privacy-friendly analytics

### Infrastructure
- **Traefik** - Reverse proxy with automatic SSL
- **Cloudflare Tunnel** - Secure external access
- **PostgreSQL** - Central database
- **InfluxDB** - Time-series data
- **Portainer** - Docker management

## Tech Stack

- **Docker & Docker Compose** - Container orchestration
- **Traefik** - Reverse proxy & SSL termination
- **Cloudflare** - DNS, CDN & Tunnel
- **Let's Encrypt** - SSL certificates

## Related

- [[projects/friday|Friday]] - AI assistant running on this infrastructure
- [[posts/how-to-manage-passwords|Password Management]] - Using KeePass synced via Nextcloud

## Links

- [GitHub Repository](https://github.com/arturgoms/homelab)
