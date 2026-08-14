"""Durable, aggregate-only usage statistics for the homepage social-proof
counter.

What is stored: ONLY two aggregate numbers' worth of data -- a single
lifetime counter and one timestamp row per successful clean (for the
rolling 24-hour window, pruned continuously). No filenames, no file
contents, no IP addresses, no user identifiers, nothing about any upload
ever touches this database. Uploaded files remain temporary and are
deleted exactly as before; this is a separate, tiny SQLite file.

Persistence: the SQLite file lives on a dedicated writable volume
(``/data`` in production, see docker-compose.prod.yml) so the lifetime
and rolling-24h numbers survive container restart, app restart, VPS
reboot, and ``docker compose up`` recreation. The production container
stays ``read_only: true`` -- this volume is the only added writable path,
alongside the existing /tmp tmpfs.

Concurrency: every write goes through a process lock AND a single SQLite
transaction (UPDATE the counter + INSERT the event atomically), so
concurrent cleans can never lose an increment -- there is no
read-modify-write race. SQLite's own locking serializes across
connections; the in-process lock serializes the app's worker threads.

Graceful degradation: if the database cannot be opened or initialized
(e.g. a misconfigured deployment where the volume is missing and the
root filesystem is read-only), the app does NOT crash -- stats silently
become a no-op and the public-stats endpoint reports unavailability, so
the frontend simply hides the social-proof block.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from contextlib import closing

log = logging.getLogger("ghostmark.web")

_DAY_SECONDS = 24 * 60 * 60


class UsageStats:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._lock = threading.Lock()
        self._ok = False
        try:
            self._init_db()
            self._ok = True
        except Exception as exc:  # noqa: BLE001 - never let stats break startup
            log.warning("usage stats unavailable (%s); social proof disabled", exc.__class__.__name__)

    @property
    def available(self) -> bool:
        return self._ok

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS totals ("
                "  id INTEGER PRIMARY KEY CHECK (id = 1),"
                "  lifetime INTEGER NOT NULL DEFAULT 0)"
            )
            conn.execute("INSERT OR IGNORE INTO totals (id, lifetime) VALUES (1, 0)")
            conn.execute("CREATE TABLE IF NOT EXISTS clean_events (ts REAL NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clean_events_ts ON clean_events (ts)")

    def record_clean(self, now: float | None = None) -> bool:
        """Count exactly one successful cleaned file. Atomic; never raises.

        Returns True ONLY when the increment was durably committed, so the
        caller can mark the session counted only after a confirmed write
        (a transient failure returns False and can be retried later --
        the session is never permanently blocked from counting).
        """

        if not self._ok:
            return False
        now = time.time() if now is None else now
        try:
            with self._lock, closing(self._connect()) as conn, conn:
                conn.execute("UPDATE totals SET lifetime = lifetime + 1 WHERE id = 1")
                conn.execute("INSERT INTO clean_events (ts) VALUES (?)", (now,))
                conn.execute("DELETE FROM clean_events WHERE ts < ?", (now - _DAY_SECONDS,))
            return True
        except Exception as exc:  # noqa: BLE001 - a stats hiccup must never fail a real clean
            log.warning("usage stats write failed: %s", exc.__class__.__name__)
            return False

    def snapshot(self, now: float | None = None) -> tuple[int, int] | None:
        """(lifetime_total, last_24h) or None if stats are unavailable."""

        if not self._ok:
            return None
        now = time.time() if now is None else now
        try:
            with self._lock, closing(self._connect()) as conn, conn:
                conn.execute("DELETE FROM clean_events WHERE ts < ?", (now - _DAY_SECONDS,))
                lifetime = conn.execute("SELECT lifetime FROM totals WHERE id = 1").fetchone()[0]
                last_24h = conn.execute(
                    "SELECT COUNT(*) FROM clean_events WHERE ts >= ?", (now - _DAY_SECONDS,)
                ).fetchone()[0]
                return int(lifetime), int(last_24h)
        except Exception as exc:  # noqa: BLE001
            log.warning("usage stats read failed: %s", exc.__class__.__name__)
            return None
