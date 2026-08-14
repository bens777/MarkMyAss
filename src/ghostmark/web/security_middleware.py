"""ASGI middleware for running GhostMark's web UI on the public internet.

Two independent concerns, kept in separate middleware classes:

- ``SecurityHeadersMiddleware``: sets defensive response headers on every
  response (CSP, no-sniff, no-frame, etc). GhostMark intentionally never
  adds CORS headers -- the frontend is same-origin only, so there is no
  legitimate cross-origin caller and no ``Access-Control-Allow-Origin`` is
  ever set.
- ``RateLimitMiddleware``: a simple in-memory sliding-window limiter per
  client IP, applied only to ``/api/*`` routes. This is intentionally
  lightweight (no Redis, no external service) since GhostMark is meant to
  stay a small, dependency-light tool -- see ``GHOSTMARK_RATE_LIMIT_PER_MINUTE``.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), interest-cohort=()"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["Server"] = "GhostMark"
        return response


def _client_ip(request: Request) -> str:
    """The caller's IP for rate limiting, behind exactly ONE trusted proxy.

    Supported topology (current production): Internet -> Caddy ->
    127.0.0.1:8765 -> app. Caddy (>=2.5) IGNORES X-Forwarded-For arriving
    from untrusted clients by default ("the proxy will ignore their
    values from incoming requests, to prevent spoofing" -- Caddy
    reverse_proxy docs), so the header the app receives contains only the
    real client address.

    Defense in depth for THAT topology: we take the RIGHTMOST entry
    rather than the first. With a single trusted reverse proxy the
    rightmost entry is the address the proxy itself observed and is the
    only part of the chain a client can never forge -- correct both when
    the proxy strips inbound XFF (modern Caddy) and when a proxy appends
    to it (the older/other common behavior, where trusting the FIRST
    entry would let any client spoof its way past per-IP rate limiting).

    NOT a universal rule: if a CDN or any second proxy layer is ever put
    in front of Caddy, the rightmost entry becomes the CDN's OWN address
    (rate limiting would lump all visitors together), and picking the
    real client requires walking the chain right-to-left past an
    explicitly configured list of trusted proxy IPs. Re-audit this
    function (and Caddy's trusted_proxies) before any such change.
    """

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    if request.client:
        return request.client.host
    return "unknown"


# Presence heartbeats live in their own rate-limit bucket so a roomful of
# tabs behind one NAT IP can never eat the (much smaller) cleaner-API
# quota. One tab beats every ~45s (~1.3 req/min), so 120/min/IP supports
# ~90 concurrent tabs behind a single shared IP while still capping abuse
# at 2 requests/second/IP. Same in-memory sliding window, same
# no-IP-retention behavior as the main limiter.
PRESENCE_REQUESTS_PER_MINUTE = 120


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limit, applied only to /api/ routes.

    Two independent buckets per client IP: the cleaner/API bucket
    (``requests_per_minute``, from GHOSTMARK_RATE_LIMIT_PER_MINUTE) and a
    dedicated presence bucket for ``/api/presence/*``
    (``presence_requests_per_minute``) -- so heartbeats never consume the
    quota real inspect/clean/verify work needs, and vice versa.
    """

    def __init__(
        self,
        app,
        *,
        requests_per_minute: int,
        window_seconds: int = 60,
        presence_requests_per_minute: int = PRESENCE_REQUESTS_PER_MINUTE,
    ) -> None:
        super().__init__(app)
        self._limits = {"api": requests_per_minute, "presence": presence_requests_per_minute}
        self._window = window_seconds
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        bucket = "presence" if request.url.path.startswith("/api/presence/") else "api"
        ip = _client_ip(request)
        now = time.time()
        with self._lock:
            hits = self._hits[(bucket, ip)]
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._limits[bucket]:
                retry_after = max(1, int(self._window - (now - hits[0])))
                return JSONResponse(
                    {"detail": "Too many requests. Please slow down and try again shortly."},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

        return await call_next(request)
