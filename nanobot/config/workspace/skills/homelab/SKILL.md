# Homelab Skill

Monitor and check self-hosted services.

## When to Use

- "Check homelab" / "how are my services?" → run `service-check.sh`
- "System info" / "disk space" / "CPU" → run `system-info.sh`
- Specific service check → run `service-check.sh [service-name]`

## How to Run

```
exec: bash /root/.nanobot/workspace/skills/homelab/scripts/service-check.sh
exec: bash /root/.nanobot/workspace/skills/homelab/scripts/service-check.sh grafana
exec: bash /root/.nanobot/workspace/skills/homelab/scripts/system-info.sh
```

## Services

| Service | URL |
|---------|-----|
| Portainer | http://${HOMELAB_IP}:9000 |
| Traefik | http://traefik.arturgomes.com/ |
| Dashy | https://dashy.arturgomes.com/ |
| Home Assistant | http://${HOMELAB_IP}:8123 |
| Immich | http://${HOMELAB_IP}:3001 |
| n8n | http://${HOMELAB_IP}:5678 |
| Grafana | http://${HOMELAB_IP}:8087 |
| InfluxDB | http://${HOMELAB_IP}:8086/health |
| InfluxDB 1.x | http://${HOMELAB_IP}:8088/ping |
| Prometheus | http://${HOMELAB_IP}:9090 |
| Graphite | http://${HOMELAB_IP}:8050 |
| Whisper ASR | http://${HOMELAB_IP}:8001 |
| Stable Diffusion | http://${HOMELAB_IP}:8002 |
| Open WebUI | http://${HOMELAB_IP}:8010 |
| SearXNG | http://${HOMELAB_IP}:8888 |
| Syncthing | http://${HOMELAB_IP}:8384 |
| Glances | http://${HOMELAB_IP}:61208/api/4/status |

## Interpreting Results

- Report as: Service ✓ or Service ✗ (with HTTP status or error)
- If all up: "All 17 services healthy"
- If some down: lead with the failures
