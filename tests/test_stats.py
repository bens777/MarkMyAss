"""Durable, aggregate-only usage counter for the homepage social proof."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig
from ghostmark.web.stats import UsageStats


def _config(stats_db_path, **overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/",
        public_url="https://markmyass.com",
        session_ttl_seconds=480,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=10,
        stats_db_path=str(stats_db_path),
    )
    base.update(overrides)
    return WebConfig(**base)


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "stats.db"


@pytest.fixture()
def client(db_path):
    return TestClient(create_app(_config(db_path)))


# --- Engine ------------------------------------------------------------------------------


def test_record_increments_lifetime_and_24h(db_path):
    s = UsageStats(str(db_path))
    assert s.snapshot() == (0, 0)
    s.record_clean()
    s.record_clean()
    assert s.snapshot() == (2, 2)


def test_rolling_window_drops_old_events_but_keeps_lifetime(db_path):
    s = UsageStats(str(db_path))
    now = 1_000_000.0
    s.record_clean(now=now - 2 * 24 * 3600)  # 2 days ago
    s.record_clean(now=now - 3600)           # 1 hour ago
    s.record_clean(now=now)                  # now
    total, last24 = s.snapshot(now=now)
    assert total == 3          # lifetime keeps every clean ever
    assert last24 == 2         # only the two within 24h


def test_counters_survive_restart(db_path):
    s1 = UsageStats(str(db_path))
    s1.record_clean()
    s1.record_clean()
    s1.record_clean()
    # Simulate a full process/container restart: brand-new instance, same file.
    s2 = UsageStats(str(db_path))
    total, last24 = s2.snapshot()
    assert total == 3 and last24 == 3


def test_concurrent_increments_are_not_lost(db_path):
    s = UsageStats(str(db_path))
    n_threads, per_thread = 8, 50

    def worker():
        for _ in range(per_thread):
            s.record_clean()

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total, last24 = s.snapshot()
    assert total == n_threads * per_thread == 400
    assert last24 == 400


def test_record_clean_returns_true_on_confirmed_write(db_path):
    s = UsageStats(str(db_path))
    assert s.record_clean() is True
    assert s.snapshot() == (1, 1)


def test_degraded_db_never_crashes_and_reports_false(tmp_path):
    # Point at an un-creatable path (a file where a directory is expected).
    bad = tmp_path / "afile"
    bad.write_text("not a dir")
    s = UsageStats(str(bad / "nested" / "stats.db"))
    assert s.available is False
    assert s.record_clean() is False  # no-op, must not raise, reports failure
    assert s.snapshot() is None       # signals the API to hide the block


def test_session_not_marked_counted_until_write_confirmed(db_path, monkeypatch):
    """A transient stats write failure must NOT permanently block the
    session from counting: it stays un-counted and a later clean retries."""

    app = create_app(_config(db_path))
    client = TestClient(app)
    jpg = _jpeg_bytes()
    sid = client.post("/api/inspect/file", files={"file": ("x.jpg", jpg)}).json()["session_id"]
    real_record = app.state.stats.record_clean

    # First clean: stats write fails transiently. The clean itself must
    # still succeed (200), and nothing is counted.
    monkeypatch.setattr(app.state.stats, "record_clean", lambda *a, **k: False)
    assert client.post(f"/api/clean/{sid}").status_code == 200
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 0

    # Recovery: stats write works again. Re-cleaning the SAME session now
    # counts it (it was never marked counted), exactly once.
    monkeypatch.setattr(app.state.stats, "record_clean", real_record)
    assert client.post(f"/api/clean/{sid}").status_code == 200
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 1
    # And it does not double-count on a further re-clean.
    client.post(f"/api/clean/{sid}")
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 1


def test_db_stores_only_aggregate_data_no_pii(db_path):
    import sqlite3

    s = UsageStats(str(db_path))
    s.record_clean()
    conn = sqlite3.connect(str(db_path))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # Only our two aggregate tables (plus SQLite internal bookkeeping).
    assert tables <= {"totals", "clean_events", "sqlite_sequence"}
    # clean_events holds ONLY a timestamp column -- no name/ip/content/id.
    cols = [c[1] for c in conn.execute("PRAGMA table_info(clean_events)")]
    assert cols == ["ts"]
    totals_cols = [c[1] for c in conn.execute("PRAGMA table_info(totals)")]
    assert totals_cols == ["id", "lifetime"]


# --- API + increment semantics -----------------------------------------------------------


def _jpeg_bytes():
    from ghostmark.fixtures.generate import make_jpeg_fixture

    p = Path(tempfile.mkdtemp()) / "x.jpg"
    make_jpeg_fixture(p)
    return p.read_bytes()


def test_public_stats_endpoint_shape(client):
    r = client.get("/api/public-stats")
    assert r.status_code == 200
    body = r.json()
    assert body == {"files_cleaned_total": 0, "files_cleaned_last_24h": 0}
    # No personal data keys of any kind.
    assert set(body) == {"files_cleaned_total", "files_cleaned_last_24h"}


def test_successful_clean_increments_exactly_once(client):
    jpg = _jpeg_bytes()
    sid = client.post("/api/inspect/file", files={"file": ("x.jpg", jpg)}).json()["session_id"]
    # inspect alone must NOT count
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 0
    assert client.post(f"/api/clean/{sid}").status_code == 200
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 1
    assert client.get("/api/public-stats").json()["files_cleaned_last_24h"] == 1
    # re-clean the same session must NOT double count
    client.post(f"/api/clean/{sid}")
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 1


def test_inspect_only_and_failed_clean_do_not_increment(client):
    # inspect-only text
    client.post("/api/inspect/text", json={"text": "hello world"})
    # clean on a non-existent session (fails)
    assert client.post("/api/clean/does-not-exist").status_code == 404
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == 0


def test_text_clean_does_not_increment_either_metric(client):
    # The public metric is "files cleaned" -- a successful pasted-text
    # clean must NOT touch lifetime or the 24h count.
    sid = client.post("/api/inspect/text", json={"text": "hi​there"}).json()["session_id"]
    assert client.post(f"/api/clean/{sid}").status_code == 200  # clean succeeds
    stats = client.get("/api/public-stats").json()
    assert stats["files_cleaned_total"] == 0
    assert stats["files_cleaned_last_24h"] == 0


def test_only_file_cleans_are_counted_mixed(client):
    # A file clean counts; a text clean alongside it does not.
    jpg = _jpeg_bytes()
    fsid = client.post("/api/inspect/file", files={"file": ("x.jpg", jpg)}).json()["session_id"]
    tsid = client.post("/api/inspect/text", json={"text": "hello"}).json()["session_id"]
    client.post(f"/api/clean/{tsid}")   # text: not counted
    client.post(f"/api/clean/{fsid}")   # file: counted once
    stats = client.get("/api/public-stats").json()
    assert stats["files_cleaned_total"] == 1
    assert stats["files_cleaned_last_24h"] == 1


def test_full_browser_flow_increments_via_real_api(db_path):
    """End-to-end through the SAME endpoints the browser calls, in the
    same order (inspect/file -> clean -> verify -> download), against a
    real temporary stats DB -- nothing about the route/session flow is
    mocked."""

    app = create_app(_config(db_path))
    client = TestClient(app)
    jpg = _jpeg_bytes()

    # 1. upload + inspect (exactly what the frontend POSTs)
    r_inspect = client.post("/api/inspect/file", files={"file": ("photo.jpg", jpg)})
    assert r_inspect.status_code == 200
    sid = r_inspect.json()["session_id"]
    assert client.get("/api/public-stats").json() == {
        "files_cleaned_total": 0,
        "files_cleaned_last_24h": 0,
    }

    # 2. clean (the "Clean File" button -> POST /api/clean/{id})
    r_clean = client.post(f"/api/clean/{sid}")
    assert r_clean.status_code == 200

    # 3. + 4. verify then download, like the real UI, to prove they don't
    #    interfere with (or double) the count.
    assert client.post(f"/api/verify/{sid}").status_code == 200
    assert client.get(f"/api/download/{sid}").status_code == 200

    stats = client.get("/api/public-stats").json()
    assert stats["files_cleaned_total"] == 1
    assert stats["files_cleaned_last_24h"] == 1

    # The app's OWN stats instance (not a fresh one) must agree -- catches
    # any wiring bug where the route and the endpoint use different objects.
    assert app.state.stats.snapshot()[0] == 1


def test_stats_survive_store_restart_via_api(db_path):
    jpg = _jpeg_bytes()
    c1 = TestClient(create_app(_config(db_path)))
    sid = c1.post("/api/inspect/file", files={"file": ("x.jpg", jpg)}).json()["session_id"]
    c1.post(f"/api/clean/{sid}")
    assert c1.get("/api/public-stats").json()["files_cleaned_total"] == 1
    # New app instance (new store, new sessions) on the SAME db file.
    c2 = TestClient(create_app(_config(db_path)))
    assert c2.get("/api/public-stats").json()["files_cleaned_total"] == 1


# --- Frontend scaffolding ----------------------------------------------------------------


def test_homepage_has_social_proof_scaffolding(client):
    html = client.get("/").text
    assert 'id="social-proof" class="social-proof hidden"' in html  # hidden until real data
    assert "files cleaned with MarkMyAss" in html
    assert 'id="social-proof-count"' in html


def test_homepage_no_longer_shows_24h_line(client):
    # The secondary "X cleaned in the last 24 hours" line was removed from
    # the UI (frontend cleanup); the backend metric may still be returned.
    html = client.get("/").text
    assert "cleaned in the last 24 hours" not in html
    assert 'id="social-proof-24h"' not in html
    assert "social-proof-dot" not in html
    js = (
        __import__("pathlib").Path(__file__).parent.parent
        / "src" / "ghostmark" / "web" / "static" / "app.js"
    ).read_text(encoding="utf-8")
    assert "files_cleaned_last_24h" not in js  # frontend no longer renders it
    # The endpoint still returns it for now.
    assert "files_cleaned_last_24h" in client.get("/api/public-stats").json()


def test_app_js_hides_social_proof_on_failure_and_zero():
    from pathlib import Path

    js = (Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "api/public-stats" in js
    assert "toLocaleString" in js               # real formatted number
    assert "SOCIAL_PROOF_MIN_TOTAL" in js       # never show 0
    assert "Math.random" not in js              # never fabricate
