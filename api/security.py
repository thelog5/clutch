"""Abuse limits and response headers for the public API (docs/SECURITY.md).

The API only serves public, read-only data, so the risks are being used as
someone else's backend, being flooded, or having a browser frame or sniff its
responses. This guard sits in front of everything:

* HTTP: a per-visitor request cap per minute, and security headers on every response
* WebSockets: only from the site's own address (once CLUTCH_CORS_ORIGINS is set),
  a cap on open streams per visitor and overall, and the same request cap

Limits are module attributes so tests (and env vars) can change them.
"""

from __future__ import annotations

import os
import time

from api import settings

RATE_LIMIT = int(os.environ.get("CLUTCH_RATE_LIMIT", "300"))  # HTTP requests + stream opens per visitor per minute
WS_MAX_TOTAL = int(os.environ.get("CLUTCH_WS_MAX", "200"))  # open replay/live streams, all visitors together
WS_MAX_PER_VISITOR = int(os.environ.get("CLUTCH_WS_MAX_PER_VISITOR", "8"))

TOO_MANY = b'{"detail":"Too many requests. Try again in a minute."}'
HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"strict-transport-security", b"max-age=31536000"),
]


def visitor(scope) -> str:
    """The caller's address: the first X-Forwarded-For hop behind Render's proxy, else the socket peer."""
    for key, value in scope.get("headers", []):
        if key == b"x-forwarded-for":
            return value.decode("latin-1").split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


def origin_allowed(scope) -> bool:
    """Browsers always send Origin on a WebSocket; other clients may not, and can't be stopped anyway."""
    if "*" in settings.CORS_ORIGINS:
        return True
    origin = next((v for k, v in scope.get("headers", []) if k == b"origin"), None)
    return origin is None or origin.decode("latin-1") in settings.CORS_ORIGINS


class Guard:
    def __init__(self, app):
        self.app = app
        self.windows: dict[str, tuple[int, int]] = {}  # visitor -> (minute, requests)
        self.streams: dict[str, int] = {}  # visitor -> open WebSockets

    def allow(self, who: str) -> bool:
        minute = int(time.time() // 60)
        start, n = self.windows.get(who, (minute, 0))
        n = n + 1 if start == minute else 1
        self.windows[who] = (minute, n)
        if len(self.windows) > 10_000:  # forget visitors from earlier minutes
            self.windows = {k: v for k, v in self.windows.items() if v[0] == minute}
        return n <= RATE_LIMIT

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            await self.http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self.websocket(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def http(self, scope, receive, send):
        if not self.allow(visitor(scope)):
            await send({"type": "http.response.start", "status": 429, "headers": [
                (b"content-type", b"application/json"), (b"retry-after", b"60"), *HEADERS]})  # fmt: skip
            await send({"type": "http.response.body", "body": TOO_MANY})
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *HEADERS]
            await send(message)

        await self.app(scope, receive, send_with_headers)

    async def websocket(self, scope, receive, send):
        who = visitor(scope)
        if (
            not origin_allowed(scope)
            or not self.allow(who)
            or sum(self.streams.values()) >= WS_MAX_TOTAL
            or self.streams.get(who, 0) >= WS_MAX_PER_VISITOR
        ):
            await receive()  # websocket.connect
            await send({"type": "websocket.close", "code": 1008})  # refused before the handshake: HTTP 403
            return
        self.streams[who] = self.streams.get(who, 0) + 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.streams[who] -= 1
            if self.streams[who] <= 0:
                del self.streams[who]
