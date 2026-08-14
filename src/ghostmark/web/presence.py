"""Anonymous, ephemeral, in-memory presence counting for the live
"pirates aboard" indicator.

Privacy model: the ONLY thing ever stored is a client-generated random
session ID mapped to a last-seen monotonic timestamp -- no IP, no
user agent, no account, no cookie, nothing persisted, nothing logged.
IDs expire after a short TTL and the whole registry dies with the
process. Only the aggregate count is ever exposed.

Multi-worker / restart semantics (documented limitation): the registry
is per-process, which is exact for the current single-Uvicorn-worker
production deployment. A container restart resets the count to zero,
which is acceptable for this lightweight feature. If MarkMyAss ever
scales to multiple workers or replicas, presence would need shared
state (e.g. Redis) -- deliberately NOT added today.

Memory is bounded twice over: session IDs are validated against a
strict alphabet/length, and the registry refuses new sessions beyond
``max_sessions`` (existing sessions keep refreshing fine), so a
flooder can never grow it past a few hundred KB.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable

# Client IDs come from crypto.randomUUID() with dashes stripped (32 hex
# chars), but any 16-64 chars of URL-safe alphabet are accepted so the
# client implementation can evolve without a server change.
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")

DEFAULT_TTL_SECONDS = 180  # "active" = heartbeat within the last 3 minutes
DEFAULT_MAX_SESSIONS = 2000  # hard memory bound; far above realistic traffic


def is_valid_session_id(session_id: object) -> bool:
    return isinstance(session_id, str) and bool(_SESSION_ID_RE.fullmatch(session_id))


class PresenceRegistry:
    """Thread-safe {anonymous session id -> last seen} map with TTL expiry."""

    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._clock = clock
        self._sessions: dict[str, float] = {}
        self._lock = threading.Lock()

    def _prune_locked(self, now: float) -> None:
        cutoff = now - self.ttl_seconds
        expired = [sid for sid, seen in self._sessions.items() if seen < cutoff]
        for sid in expired:
            del self._sessions[sid]

    def beat(self, session_id: str) -> int:
        """Record a heartbeat and return the current active count.

        Unknown IDs beyond the max_sessions cap are ignored (the count is
        still returned) so a flood of fabricated IDs cannot grow memory.
        """

        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            if session_id in self._sessions or len(self._sessions) < self.max_sessions:
                self._sessions[session_id] = now
            return len(self._sessions)

    def count(self) -> int:
        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            return len(self._sessions)

    def snapshot(self) -> tuple[int, bool]:
        """(active count, at-cap?) in one locked pass.

        ``capped`` means the registry is full: additional visitors may
        exist but can't be admitted, so the UI must say "N+" rather than
        pretending the number is exact.
        """

        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            n = len(self._sessions)
            return n, n >= self.max_sessions
