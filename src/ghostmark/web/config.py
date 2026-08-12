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

    @property
    def is_hosted(self) -> bool:
        return self.mode == "hosted"


def _normalize_base_path(raw: str) -> str:
    if not raw or raw == "/":
        return "/"
    path = "/" + raw.strip("/") + "/"
    return path


def load_config() -> WebConfig:
    mode = _env_str("GHOSTMARK_MODE", "local").lower()
    if mode not in ("local", "hosted"):
        mode = "local"

    ttl_minutes = _env_int("GHOSTMARK_SESSION_TTL_MINUTES", _DEFAULT_SESSION_TTL_MINUTES)
    ttl_minutes = max(1, min(ttl_minutes, _MAX_SESSION_TTL_MINUTES))

    return WebConfig(
        mode=mode,
        base_path=_normalize_base_path(_env_str("GHOSTMARK_BASE_PATH", "/")),
        public_url=_env_str("GHOSTMARK_PUBLIC_URL", "https://moseisley.sh/ghostmark"),
        session_ttl_seconds=ttl_minutes * 60,
        rate_limit_per_minute=_env_int("GHOSTMARK_RATE_LIMIT_PER_MINUTE", 20),
        max_concurrent_jobs=_env_int("GHOSTMARK_MAX_CONCURRENT", 4),
        processing_timeout_seconds=_env_int("GHOSTMARK_PROCESSING_TIMEOUT_SECONDS", 30),
        max_upload_mb=_env_int("GHOSTMARK_MAX_UPLOAD_MB", 50),
    )
