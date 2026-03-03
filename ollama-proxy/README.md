# Ollama WOL Proxy

Transparent reverse proxy that auto-wakes the Ollama server (192.168.1.18) via Wake-on-LAN when a request comes in, and auto-suspends it when idle.

## How it works

```
nanobot (host) → localhost:11434 (proxy) → 192.168.1.18:11434 (ollama)
                                                ↑
                                         WOL if unreachable
```

1. **Proxy** runs on this server (Docker, host network) listening on port 11434
2. On each request, it checks if the Ollama machine is reachable (TCP connect, cached 5s)
3. If unreachable, sends a WOL magic packet and polls until the machine is up (timeout 90s)
4. Forwards the request with full streaming support (600s timeout for large inferences)
5. Concurrent requests during a wake share a single WOL cycle via asyncio lock

On the Ollama machine:
1. A **systemd timer** runs every 2 minutes checking if the machine should sleep
2. It suspends when: no models are loaded in Ollama AND no SSH sessions are active
3. Ollama auto-unloads models after 5 minutes of inactivity (default keep_alive)
4. So the machine sleeps ~7 minutes after the last request (5min unload + 2min timer)

## Setup

### This server (proxy)

```bash
cd /srv/ollama-proxy
docker compose up -d
```

### Ollama machine (192.168.1.18)

Copy and run the setup script with sudo:

```bash
scp remote/setup.sh artur@192.168.1.18:/tmp/setup.sh
ssh artur@192.168.1.18 "sudo bash /tmp/setup.sh"
```

This installs:
- WOL enabled on `eno1` (persisted via networkd-dispatcher)
- `/usr/local/bin/ollama-autosleep.sh` — idle check script
- `ollama-autosleep.timer` — systemd timer (every 2min, first check 5min after boot)

The individual files are in `remote/` for reference.

## Configuration

All config is in `.env`:

| Variable | Description |
|----------|-------------|
| `OLLAMA_HOST` | Ollama machine IP |
| `OLLAMA_PORT` | Ollama port (default 11434) |
| `LISTEN_PORT` | Proxy listen port (default 11434) |
| `MAC_ADDRESS` | Ollama machine MAC for WOL |
| `BROADCAST_IP` | Broadcast address for WOL packets |

## Verification

```bash
# Check proxy logs
docker logs ollama-proxy

# Test proxy (machine awake)
curl http://127.0.0.1:11434/v1/models

# Check autosleep timer on ollama machine
ssh artur@192.168.1.18 "systemctl status ollama-autosleep.timer"

# Watch autosleep decisions
ssh artur@192.168.1.18 "journalctl -t ollama-autosleep -f"

# Check loaded models / time until unload
curl -s http://192.168.1.18:11434/api/ps
```
