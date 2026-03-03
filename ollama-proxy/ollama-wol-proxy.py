#!/usr/bin/env python3
"""Transparent reverse proxy for Ollama with Wake-on-LAN support.

Intercepts requests to Ollama, wakes the machine via WOL if unreachable,
waits for it to come up, then forwards the request with full streaming support.
"""

import asyncio
import logging
import os
import socket
import struct
import time

from aiohttp import ClientSession, ClientTimeout, web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ollama-wol-proxy")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "192.168.1.18")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "11434"))
MAC_ADDRESS = os.environ.get("MAC_ADDRESS", "")
BROADCAST_IP = os.environ.get("BROADCAST_IP", "192.168.1.255")

WOL_TIMEOUT = 90  # seconds to wait for machine to wake
WOL_POLL_INTERVAL = 2  # seconds between reachability checks
REACHABLE_CACHE_TTL = 5  # seconds to cache reachability status
REQUEST_TIMEOUT = 600  # seconds for proxied request timeout

_last_reachable_check: float = 0
_last_reachable_result: bool = False
_wake_lock = asyncio.Lock()


def send_wol(mac: str) -> None:
    """Send a Wake-on-LAN magic packet via UDP broadcast."""
    mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
    magic = b"\xff" * 6 + mac_bytes * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic, (BROADCAST_IP, 9))
    log.info("WOL magic packet sent to %s", mac)


async def check_reachable() -> bool:
    """Check if Ollama is reachable via TCP connect, with caching."""
    global _last_reachable_check, _last_reachable_result

    now = time.monotonic()
    if now - _last_reachable_check < REACHABLE_CACHE_TTL:
        return _last_reachable_result

    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(OLLAMA_HOST, OLLAMA_PORT), timeout=3
        )
        writer.close()
        await writer.wait_closed()
        _last_reachable_result = True
    except (OSError, asyncio.TimeoutError):
        _last_reachable_result = False

    _last_reachable_check = now
    return _last_reachable_result


async def ensure_awake() -> bool:
    """Ensure the Ollama machine is awake, sending WOL if needed.

    Uses a lock so concurrent requests share a single wake cycle.
    Returns True if machine is reachable, False if wake failed.
    """
    if await check_reachable():
        return True

    async with _wake_lock:
        # Re-check after acquiring lock (another request may have woken it)
        if await check_reachable():
            return True

        if not MAC_ADDRESS:
            log.error("Ollama unreachable and no MAC_ADDRESS configured")
            return False

        send_wol(MAC_ADDRESS)

        deadline = time.monotonic() + WOL_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(WOL_POLL_INTERVAL)
            # Bypass cache for wake polling
            global _last_reachable_check
            _last_reachable_check = 0
            if await check_reachable():
                log.info("Ollama machine is awake")
                # Give ollama service a moment to be ready
                await asyncio.sleep(2)
                return True

        log.error("Ollama machine did not wake within %ds", WOL_TIMEOUT)
        return False


async def proxy_handler(request: web.Request) -> web.StreamResponse:
    """Forward request to Ollama, waking the machine if needed."""
    if not await ensure_awake():
        return web.Response(
            status=503,
            text="Ollama server unreachable and could not be woken via WOL",
        )

    target_url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}{request.path_qs}"

    body = await request.read()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "transfer-encoding")
    }

    timeout = ClientTimeout(total=REQUEST_TIMEOUT, sock_connect=10)
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=body,
            ) as upstream:
                response = web.StreamResponse(
                    status=upstream.status,
                    headers={
                        k: v
                        for k, v in upstream.headers.items()
                        if k.lower()
                        not in ("transfer-encoding", "content-encoding", "content-length")
                    },
                )

                content_length = upstream.headers.get("content-length")
                if content_length:
                    response.content_length = int(content_length)

                await response.prepare(request)

                async for chunk in upstream.content.iter_any():
                    await response.write(chunk)

                await response.write_eof()
                return response

    except Exception as e:
        log.error("Proxy error: %s", e)
        # Invalidate reachability cache on error
        global _last_reachable_check
        _last_reachable_check = 0
        return web.Response(status=502, text=f"Proxy error: {e}")


app = web.Application()
app.router.add_route("*", "/{path_info:.*}", proxy_handler)

if __name__ == "__main__":
    log.info(
        "Starting WOL proxy: listening on :%d, forwarding to %s:%d",
        LISTEN_PORT,
        OLLAMA_HOST,
        OLLAMA_PORT,
    )
    web.run_app(app, host="0.0.0.0", port=LISTEN_PORT, print=None)
