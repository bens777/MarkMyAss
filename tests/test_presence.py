"""Live presence counter: anonymous, aggregate-only, bounded, honest."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig
from ghostmark.web.presence import PresenceRegistry, is_valid_session_id

SID_A = "a" * 32
SID_B = "b" * 32


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/",
        public_url="https://markmyass.com",
        session_ttl_seconds=480,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=10,
    )
    base.update(overrides)
    return WebConfig(**base)


@pytest.fixture()
def client():
    return TestClient(create_app(_config()))


# --- Registry unit tests (fake clock -- no sleeping) -------------------------------------


def test_heartbeat_creates_active_session():
    reg = PresenceRegistry(ttl_seconds=180, clock=lambda: 100.0)
    assert reg.beat(SID_A) == 1
    assert reg.count() == 1


def test_repeated_heartbeat_does_not_double_count():
    reg = PresenceRegistry(ttl_seconds=180, clock=lambda: 100.0)
    for _ in range(5):
        reg.beat(SID_A)
    assert reg.count() == 1


def test_second_session_increments_count():
    reg = PresenceRegistry(ttl_seconds=180, clock=lambda: 100.0)
    reg.beat(SID_A)
    assert reg.beat(SID_B) == 2


def test_expired_session_disappears_after_ttl():
    now = [100.0]
    reg = PresenceRegistry(ttl_seconds=180, clock=lambda: now[0])
    reg.beat(SID_A)
    now[0] = 100.0 + 179  # still inside the 3-minute window
    assert reg.count() == 1
    now[0] = 100.0 + 181  # past the window
    assert reg.count() == 0


def test_refreshing_heartbeat_extends_lifetime():
    now = [100.0]
    reg = PresenceRegistry(ttl_seconds=180, clock=lambda: now[0])
    reg.beat(SID_A)
    now[0] += 170
    reg.beat(SID_A)  # refresh just before expiry
    now[0] += 170
    assert reg.count() == 1  # 340s after first beat, but only 170s after refresh


def test_registry_is_bounded():
    reg = PresenceRegistry(ttl_seconds=180, max_sessions=50, clock=lambda: 100.0)
    for i in range(500):
        reg.beat(f"flood{i:059d}")  # valid 64-char ids
    assert reg.count() == 50  # cap holds; excess ids ignored
    # Existing sessions can still refresh at the cap.
    assert reg.beat("flood" + "0" * 58 + "1") == 50


def test_session_id_validation():
    assert is_valid_session_id("a" * 16)
    assert is_valid_session_id("A1-_" * 8)
    assert not is_valid_session_id("short")  # < 16
    assert not is_valid_session_id("x" * 65)  # > 64
    assert not is_valid_session_id("bad id with spaces!")
    assert not is_valid_session_id("")
    assert not is_valid_session_id(None)
    assert not is_valid_session_id(12345)


# --- API tests ---------------------------------------------------------------------------


def test_heartbeat_endpoint_counts_and_returns_aggregate_only(client):
    r = client.post("/api/presence/heartbeat", json={"sid": SID_A})
    assert r.status_code == 200
    assert r.json() == {"active": 1, "capped": False}
    # Same session again: no double count.
    assert client.post("/api/presence/heartbeat", json={"sid": SID_A}).json() == {
        "active": 1,
        "capped": False,
    }
    # A second anonymous session increments.
    assert client.post("/api/presence/heartbeat", json={"sid": SID_B}).json() == {
        "active": 2,
        "capped": False,
    }


def test_count_endpoint_exposes_only_the_number(client):
    client.post("/api/presence/heartbeat", json={"sid": SID_A})
    r = client.get("/api/presence/count")
    assert r.status_code == 200
    assert r.json() == {"active": 1, "capped": False}
    assert SID_A not in r.text  # never leak registry contents


@pytest.mark.parametrize(
    "payload",
    [
        {"sid": "short"},
        {"sid": "x" * 65},
        {"sid": "bad id!"},
        {"sid": ""},
        {"sid": 123},
        {},
        {"sid": SID_A, "extra": "ignored-but-never-stored"},
    ],
)
def test_malformed_heartbeats_rejected_or_sanitized(client, payload):
    r = client.post("/api/presence/heartbeat", json=payload)
    if payload.get("sid") == SID_A:
        # Extra fields are dropped by the schema -- only sid is ever read.
        assert r.status_code == 200
        assert r.json() == {"active": 1, "capped": False}
    else:
        assert r.status_code in (400, 422)
        assert client.get("/api/presence/count").json() == {"active": 0, "capped": False}


def test_heartbeat_does_not_interfere_with_cleaner_api(client):
    client.post("/api/presence/heartbeat", json={"sid": SID_A})
    r = client.post("/api/inspect/text", json={"text": "hello​world"})
    assert r.status_code == 200
    assert "session_id" in r.json()
    # And the cleaner session store is a different thing entirely.
    assert client.get("/api/presence/count").json() == {"active": 1, "capped": False}


# --- Dedicated rate-limit bucket + honest cap state --------------------------------------


def test_presence_does_not_consume_cleaner_api_quota():
    """With a tiny cleaner quota, a burst of heartbeats must not starve
    real inspect calls -- presence lives in its own bucket."""

    client = TestClient(create_app(_config(rate_limit_per_minute=3)))
    for _ in range(10):
        assert client.post("/api/presence/heartbeat", json={"sid": SID_A}).status_code == 200
    assert client.post("/api/inspect/text", json={"text": "hello"}).status_code == 200


def test_cleaner_api_quota_is_not_weakened():
    client = TestClient(create_app(_config(rate_limit_per_minute=3)))
    for _ in range(3):
        assert client.post("/api/inspect/text", json={"text": "x"}).status_code == 200
    assert client.post("/api/inspect/text", json={"text": "x"}).status_code == 429
    # ...while presence keeps working from its own bucket.
    assert client.post("/api/presence/heartbeat", json={"sid": SID_A}).status_code == 200


def test_presence_has_its_own_abuse_protection():
    """The dedicated presence bucket still 429s a flood from one IP."""

    client = TestClient(create_app(_config()))
    statuses = [
        client.post("/api/presence/heartbeat", json={"sid": SID_A}).status_code
        for _ in range(121)
    ]
    assert statuses[:120] == [200] * 120
    assert statuses[120] == 429


def test_shared_ip_heartbeats_behave_reasonably():
    """Many tabs behind one NAT IP: distinct sessions all register and
    all count, well within the 120/min presence budget."""

    client = TestClient(create_app(_config()))
    for i in range(30):
        r = client.post("/api/presence/heartbeat", json={"sid": f"tab{i:029d}"})
        assert r.status_code == 200
    assert client.get("/api/presence/count").json() == {"active": 30, "capped": False}


def test_cap_state_reports_capped_not_falsely_exact():
    client = TestClient(create_app(_config()))
    client.app.state.presence.max_sessions = 3
    for i in range(5):
        r = client.post("/api/presence/heartbeat", json={"sid": f"cap{i:029d}"})
        assert r.status_code == 200
    assert r.json() == {"active": 3, "capped": True}
    assert client.get("/api/presence/count").json() == {"active": 3, "capped": True}


def test_registry_snapshot_reports_cap():
    reg = PresenceRegistry(ttl_seconds=180, max_sessions=2, clock=lambda: 100.0)
    reg.beat(SID_A)
    assert reg.snapshot() == (1, False)
    reg.beat(SID_B)
    assert reg.snapshot() == (2, True)


# --- Display copy (client-side literals) -------------------------------------------------


def _app_js() -> str:
    path = Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "app.js"
    return path.read_text(encoding="utf-8")


def test_copy_singular_plural_and_zero_states():
    js = _app_js()
    assert "1 pirate is hunting hidden AI traces right now" in js
    assert "pirates are hunting hidden AI traces right now" in js
    assert "}+ pirates are hunting hidden AI traces right now" in js  # capped "N+" state
    assert "be the first aboard" in js
    # The honesty rules: no fabricated floor, no fake randomness.
    assert "Math.random" not in js


def test_homepage_has_presence_line_scaffolding():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'id="presence-line" class="presence-line hidden"' in html  # hidden until real data
    assert 'id="presence-text"' in html
