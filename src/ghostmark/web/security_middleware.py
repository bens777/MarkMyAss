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
    """The caller's IP, trusting X-Forwarded-For from the reverse proxy.

    GhostMark's web app is only ever reachable through the deployment's
    reverse proxy (see DEPLOY_MOSEISLEY.md) -- it is not bound to a public
    interface itself -- so the proxy is the only thing that can set this
    header in practice.
    """

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limit, applied only to /api/ routes."""

    def __init__(self, app, *, requests_per_minute: int, window_seconds: int = 60) -> None:
        super().__init__(app)
        self._limit = requests_per_minute
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        ip = _client_ip(request)
        now = time.time()
        with self._lock:
            hits = self._hits[ip]
            while hits and now - hits[0] > self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                retry_after = max(1, int(self._window - (now - hits[0])))
                return JSONResponse(
                    {"detail": "Too many requests. Please slow down and try again shortly."},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

        return await call_next(request)
