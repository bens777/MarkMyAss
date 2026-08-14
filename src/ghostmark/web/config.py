"""Environment-driven configuration for the web app.

Every knob here has a safe default for running GhostMark locally
(``ghostmark ui``). The production deployment (docker-compose.prod.yml)
overrides a handful of these for public internet exposure -- a lower
upload limit, a shorter session TTL, rate limiting, and "hosted" mode
copy in the UI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_MAX_SESSION_TTL_MINUTES = 15
_DEFAULT_SESSION_TTL_MINUTES = 12


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


@dataclass(frozen=True)
class WebConfig:
    mode: str  # "local" | "hosted"
    base_path: str  # always starts and ends with "/", e.g. "/" or "/ghostmark/"
    public_url: str
    session_ttl_seconds: int
    rate_limit_per_minute: int
    max_concurrent_jobs: int
    processing_timeout_seconds: int
    max_upload_mb: int
    # Path to the durable, aggregate-only usage-stats SQLite DB. None ->
    # a default temp-dir file (fine for local/dev; ephemeral). Production
    # sets GHOSTMARK_STATS_DB to a file on a dedicated writable volume so
    # the counter survives restarts (see docker-compose.prod.yml).
    stats_db_path: str | None = None

    @property
    def is_hosted(self) -> bool:
        return self.mode == "hosted"


def _normalize_base_path(raw: str) -> str:
    if not raw or raw == "/":
        return "/"
    path = "/" + raw.strip("/") + "/"
    return path


_HOSTED_DEFAULT_RATE_LIMIT_PER_MINUTE = 20
# RateLimitMiddleware is always attached regardless of mode (see app.py),
# but per-IP request throttling exists to protect a PUBLIC deployment from
# abuse -- see SECURITY.md's threat model, which only lists rate limiting
# under "Hosted mode." A single local user (127.0.0.1-only, no adversarial
# exposure) legitimately doing routine batch work -- dragging in a folder
# of files through the web UI, or a script driving the API directly -- can
# easily exceed 20 requests/minute across inspect+clean+verify+download
# calls for even a handful of files. Local mode's default is high enough
# to be a non-factor for real usage while still bounding a runaway loop.
_LOCAL_DEFAULT_RATE_LIMIT_PER_MINUTE = 1000


def load_config() -> WebConfig:
    mode = _env_str("GHOSTMARK_MODE", "local").lower()
    if mode not in ("local", "hosted"):
        mode = "local"

    ttl_minutes = _env_int("GHOSTMARK_SESSION_TTL_MINUTES", _DEFAULT_SESSION_TTL_MINUTES)
    ttl_minutes = max(1, min(ttl_minutes, _MAX_SESSION_TTL_MINUTES))

    default_rate_limit = (
        _HOSTED_DEFAULT_RATE_LIMIT_PER_MINUTE if mode == "hosted" else _LOCAL_DEFAULT_RATE_LIMIT_PER_MINUTE
    )

    return WebConfig(
        mode=mode,
        base_path=_normalize_base_path(_env_str("GHOSTMARK_BASE_PATH", "/")),
        public_url=_env_str("GHOSTMARK_PUBLIC_URL", "https://markmyass.com"),
        session_ttl_seconds=ttl_minutes * 60,
        rate_limit_per_minute=_env_int("GHOSTMARK_RATE_LIMIT_PER_MINUTE", default_rate_limit),
        max_concurrent_jobs=_env_int("GHOSTMARK_MAX_CONCURRENT", 4),
        processing_timeout_seconds=_env_int("GHOSTMARK_PROCESSING_TIMEOUT_SECONDS", 30),
        max_upload_mb=_env_int("GHOSTMARK_MAX_UPLOAD_MB", 50),
        stats_db_path=(os.environ.get("GHOSTMARK_STATS_DB", "").strip() or None),
    )
