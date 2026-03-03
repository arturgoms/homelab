---
title: Auto-Sleeping My GPU Server
description: How I cut my Ollama server's power consumption by 90% with a WOL proxy that wakes it on demand and suspends it when idle
date: 2026-03-03
status: published
tags:
  - area/blog
  - topic/homelab
  - topic/ai
  - project/homelab
---

My Ollama server runs on a dedicated Ubuntu machine with an RTX 3090. It pulls 100W at idle and up to 500W under GPU load. It was running 24/7 even though I only use it a few times a day through [[friday|Friday]] and my Telegram bot. That's roughly 72 kWh/month just idling — around R$ 63/month here in Curitiba for a machine that's actually working maybe 30 minutes a day.

The fix: a transparent proxy that wakes the machine via Wake-on-LAN when a request comes in, and a systemd timer that suspends it when idle.

---

## The Architecture

```
friday (host) → localhost:11434 (proxy) → 192.168.1.18:11434 (ollama)
                                                ↑
                                         WOL if unreachable
```

The proxy sits on my [[homelab|homelab]] server (which runs 24/7 anyway for all other services). It listens on port 11434 — the same port Ollama uses. Any service that previously pointed at the Ollama machine's IP now points at `127.0.0.1:11434` instead. Zero changes to the clients.

When a request arrives:
1. Proxy checks if the Ollama machine is reachable (TCP connect, cached for 5 seconds)
2. If it's up, forward the request immediately — no overhead
3. If it's down, send a WOL magic packet and poll every 2 seconds until it wakes (up to 90 seconds)
4. Forward the request with full streaming support

On the Ollama machine side, a systemd timer checks every 2 minutes:
1. Are any models loaded? (Ollama auto-unloads after 5 minutes of inactivity)
2. Is anyone SSH'd in?
3. If both are no → suspend

So the flow is: I send a Telegram message → [friday] hits the proxy → proxy wakes the machine (~15 seconds) → Ollama serves the request → 5 minutes of silence → model unloads → next timer tick → machine suspends.

---

## The WOL Proxy

The proxy is a single Python file using `aiohttp`. It runs in a Docker container with `network_mode: host` so it can send UDP broadcast packets for WOL and listen on port 11434 directly.

### `ollama-wol-proxy.py`

```python
#!/usr/bin/env python3
import asyncio
import logging
import os
import socket
import time

from aiohttp import ClientSession, ClientTimeout, web

log = logging.getLogger("ollama-wol-proxy")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "192.168.1.18")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "11434"))
MAC_ADDRESS = os.environ.get("MAC_ADDRESS", "")
BROADCAST_IP = os.environ.get("BROADCAST_IP", "192.168.1.255")

WOL_TIMEOUT = 90
WOL_POLL_INTERVAL = 2
REACHABLE_CACHE_TTL = 5
REQUEST_TIMEOUT = 600

_last_reachable_check: float = 0
_last_reachable_result: bool = False
_wake_lock = asyncio.Lock()
```

The key design decisions:

**Reachability caching** — Every request checks if Ollama is up via a TCP connect attempt, but the result is cached for 5 seconds. This avoids hammering the network on every request while still detecting a suspended machine quickly.

**Wake lock** — If 5 requests arrive while the machine is asleep, you don't want 5 WOL packets and 5 independent polling loops. An `asyncio.Lock()` ensures only one wake cycle runs at a time. All concurrent requests wait on the same lock and proceed together once the machine is up.

**Streaming support** — LLM responses are streamed token-by-token. The proxy uses `iter_any()` to forward chunks as they arrive, so the user sees tokens appearing in real time, not a delayed bulk response.

The WOL magic packet itself is pure Python — no external dependencies:

```python
def send_wol(mac: str) -> None:
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    magic = b"\xff" * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (BROADCAST_IP, 9))
```

A WOL magic packet is just 6 bytes of `0xFF` followed by the target MAC address repeated 16 times, sent as a UDP broadcast on port 9.

### Docker Setup

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir aiohttp
COPY ollama-wol-proxy.py /app/proxy.py
CMD ["python3", "-u", "/app/proxy.py"]
```

```yaml
# docker-compose.yml
services:
  ollama-proxy:
    build: .
    container_name: ollama-proxy
    network_mode: host
    restart: unless-stopped
    env_file: .env
```

The `.env` file holds the target machine's MAC address and IP:

```
OLLAMA_HOST=192.168.1.18
OLLAMA_PORT=11434
LISTEN_PORT=11434
MAC_ADDRESS=cc:28:aa:ca:d3:00
BROADCAST_IP=192.168.1.255
```

---

## The Ollama Machine Setup

### Enabling Wake-on-LAN

WOL needs to be enabled on the NIC. On Ubuntu with a wired connection:

```bash
# Check current status
sudo ethtool eno1 | grep Wake-on
# Wake-on: d  ← disabled

# Enable it
sudo ethtool -s eno1 wol g
# Wake-on: g  ← enabled
```

This doesn't survive reboots. To persist it, create a script that runs when the network interface comes up:

```bash
# /etc/networkd-dispatcher/configuring.d/wol.sh
#!/bin/bash
ethtool -s eno1 wol g
```

Make it executable with `chmod +x`.

### The Auto-Sleep Script

This is the script that decides whether to suspend:

```bash
#!/bin/bash
# /usr/local/bin/ollama-autosleep.sh

# Don't suspend if models are loaded (ollama unloads after 5min idle)
MODELS_LOADED=$(curl -sf http://localhost:11434/api/ps 2>/dev/null | grep -c '"model"' || true)
[ "${MODELS_LOADED:-0}" -gt 0 ] && exit 0

# Don't suspend if someone is logged in via SSH
LOGGED_IN=$(who | wc -l)
[ "$LOGGED_IN" -gt 0 ] && exit 0

logger -t ollama-autosleep "Ollama idle, suspending"
systemctl suspend
```

Two checks, both intentional:

**Models loaded** — Ollama's `/api/ps` endpoint returns currently loaded models. By default, Ollama keeps a model in memory for 5 minutes after the last request (`keep_alive`). Each new request resets this timer. So the machine won't suspend mid-conversation — only after 5 minutes of complete silence.

**SSH sessions** — If I'm SSH'd in doing maintenance, I don't want the machine to suspend under me.

I initially had more checks (uptime threshold, active TCP connections), but simplified it down to these two. The model-loaded check effectively covers the "active connection" case because Ollama won't unload while serving requests.

### Systemd Timer

The timer runs the check every 2 minutes, with a 5-minute grace period after boot to let services stabilize:

```ini
# /etc/systemd/system/ollama-autosleep.service
[Unit]
Description=Ollama auto-sleep idle check

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ollama-autosleep.sh
```

```ini
# /etc/systemd/system/ollama-autosleep.timer
[Unit]
Description=Check Ollama idle every 2 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
```

Enable with `systemctl enable --now ollama-autosleep.timer`.

Make sure your `ollama.service` is enabled too (`systemctl is-enabled ollama`) — it needs to start automatically when the machine wakes from suspend.

---

## The Client Change

The only change on the client side is swapping the IP:

```json
{
  "providers": {
    "custom": {
      "apiKey": "ollama",
      "apiBase": "http://127.0.0.1:11434/v1"
    }
  }
}
```

From `192.168.1.18` to `127.0.0.1`. That's it. The proxy is completely transparent — same port, same API, same streaming behavior.

---

## The Numbers

Here in Curitiba, Copel charges around R$ 0.88/kWh for residential.

| | Before | After |
|---|---|---|
| Daily uptime | 24h | ~1.25h |
| Idle power | 100W × 24h = 2,400 Wh | 100W × 1h = 100 Wh |
| GPU power | 350W × 2h = 700 Wh | 350W × 15min = 88 Wh |
| Monthly consumption | ~87 kWh | ~5.6 kWh |
| Monthly cost | ~R$ 77 | ~R$ 5 |
| **Annual savings** | | **~R$ 860** |

The actual savings depend on usage. Heavy usage (hours of inference daily) shifts the balance, but the idle elimination is the big win. A machine that sits idle 22 hours a day shouldn't be drawing 100W for 22 hours.

---

## Edge Cases

A few scenarios I considered:

**Machine already awake** — The TCP check is cached for 5 seconds. If the machine is up, the request forwards immediately with negligible overhead.

**Multiple requests during wake** — The asyncio lock serializes wake attempts. One WOL packet is sent, all waiting requests proceed together once the machine responds.

**Request arrives while suspending** — The auto-sleep script checks for loaded models and active connections before suspending. If a request is in-flight, Ollama will have a model loaded, so the script exits without suspending.

**WOL fails** — The proxy returns a 503 after 90 seconds. The client can retry.

**Proxy itself crashes** — Docker's `restart: unless-stopped` brings it back automatically.

---

## Key Takeaways

- WOL is a simple, reliable way to wake machines on demand — the magic packet is just a UDP broadcast
- `network_mode: host` in Docker is necessary for both UDP broadcast (WOL) and binding to a specific port on the host
- Ollama's `keep_alive` timer is the natural "idle detector" — no need to build custom activity tracking
- The proxy adds essentially zero latency when the machine is already awake (one cached TCP check)
- A systemd timer is cleaner than a cron job for periodic checks — built-in logging, dependency management, and `OnBootSec` for boot delay

---

## Updates

- **2026-03-03** — Initial publication
