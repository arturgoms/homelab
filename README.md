# Homelab

My self-hosted infrastructure running on Docker with Traefik as reverse proxy and Cloudflare Tunnel for external access.

## Architecture

```
Internet → Cloudflare Tunnel → Traefik → Docker Services
                                  ↓
                            Let's Encrypt (SSL)
```

## Services

| Service | Description | Port/URL |
|---------|-------------|----------|
| **traefik** | Reverse proxy & SSL termination | 80, 443 |
| **cloudflare** | Cloudflare Tunnel for external access | - |
| **databases** | Central PostgreSQL + InfluxDB | 5432, 8088 |
| **portainer** | Docker management UI | 9000 |

### Applications

| Service | Description | URL |
|---------|-------------|-----|
| **arturgomes.com** | Personal website (Hugo) | arturgomes.com |
| **immich** | Photo & video management | immich.arturgomes.com |
| **nextcloud** | File sync & storage | nextcloud.arturgomes.com |
| **n8n** | Workflow automation | n8n.arturgomes.com |
| **home-assistant** | Home automation | home.arturgomes.com |
| **dashy** | Dashboard | dashy.arturgomes.com |
| **umami** | Privacy-friendly analytics | umami.arturgomes.com |
| **searxng** | Privacy search engine | search.arturgomes.com |
| **openwebui** | AI chat interface | chat.arturgomes.com |
| **whisper** | Speech-to-text | whisper.arturgomes.com |
| **stable-diffusion** | Image generation | sd.arturgomes.com |
| **syncthing** | File synchronization | syncthing.arturgomes.com |
| **glances** | System monitoring | glances.arturgomes.com |

### Security & Monitoring

| Service | Description |
|---------|-------------|
| **crowdsec** | Security engine & threat detection |
| **monitoring** | Prometheus + Grafana stack |

### Databases

| Service | Description | Port |
|---------|-------------|------|
| **PostgreSQL** | Main database (shared) | 5432 |
| **InfluxDB 1.x** | Time-series (Garmin data) | 8088 |
| **MariaDB** | MySQL-compatible database | 3306 |

### Other

| Service | Description |
|---------|-------------|
| **garmin-fetch-data** | Garmin fitness data fetcher |

## Directory Structure

```
/srv/
├── traefik/              # Reverse proxy configuration
├── cloudflare/           # Cloudflare Tunnel
├── databases/            # Central PostgreSQL & InfluxDB
├── arturgomes.com/       # Personal website
├── immich/               # Photo management
├── nextcloud/            # File storage
├── n8n/                  # Automation workflows
├── home-assistant/       # Home automation
├── monitoring/           # Prometheus & Grafana
├── crowdsec/             # Security
└── ...                   # Other services
```

## Setup

### Prerequisites

- Docker & Docker Compose
- Domain with Cloudflare DNS
- Cloudflare Tunnel configured

### Networks

All services use the `exposed` Docker network for inter-container communication:

```bash
docker network create exposed
```

### Starting Services

Each service has its own `docker-compose.yml`:

```bash
cd /srv/<service>
docker compose up -d
```

### Environment Variables

Each service has a `.env.example` file. Copy and configure:

```bash
cp .env.example .env
# Edit .env with your values
```

## Security Notes

- All external traffic goes through Cloudflare Tunnel
- Traefik handles SSL certificates via Let's Encrypt
- CrowdSec provides intrusion detection
- Sensitive data stored in `.env` files (git-ignored)

## License

MIT
