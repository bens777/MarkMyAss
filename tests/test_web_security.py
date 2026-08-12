"""Public-web hardening: security headers, rate limiting, concurrency/timeout limits,
configurable upload size, MIME sniffing, generic error responses."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.security import sniff_mime_matches_extension
from ghostmark.web.app import create_app
from ghostmark.web.concurrency import BoundedRunner, ProcessingTimeoutError, ServerBusyError
from ghostmark.web.config import WebConfig, load_config


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/",
        public_url="https://moseisley.sh/ghostmark",
        session_ttl_seconds=720,
        rate_limit_per_minute=5,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=20,
    )
    base.update(overrides)
    return WebConfig(**base)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


# --- config loading ---------------------------------------------------------------


def test_load_config_defaults_to_local_mode(monkeypatch):
    monkeypatch.delenv("GHOSTMARK_MODE", raising=False)
    config = load_config()
    assert config.mode == "local"
    assert config.base_path == "/"


def test_load_config_clamps_ttl_to_max_15_minutes(monkeypatch):
    monkeypatch.setenv("GHOSTMARK_SESSION_TTL_MINUTES", "999")
    config = load_config()
    assert config.session_ttl_seconds == 15 * 60


def test_load_config_normalizes_base_path(monkeypatch):
    monkeypatch.setenv("GHOSTMARK_BASE_PATH", "ghostmark")
    config = load_config()
    assert config.base_path == "/ghostmark/"


# --- security headers --------------------------------------------------------------


def test_security_headers_present():
    client = TestClient(create_app(_config(rate_limit_per_minute=1000)))
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" in resp.headers
    assert resp.headers["server"] == "GhostMark"


def test_no_cors_headers_ever_present():
    client = TestClient(create_app(_config(rate_limit_per_minute=1000)))
    resp = client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in {h.lower() for h in resp.headers}


# --- rate limiting ------------------------------------------------------------------


def test_rate_limit_blocks_after_threshold():
    client = TestClient(create_app(_config(rate_limit_per_minute=3)))
    statuses = [
        client.post("/api/inspect/text", json={"text": "hello"}).status_code for _ in range(5)
    ]
    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]


def test_rate_limit_does_not_apply_to_health_or_static():
    client = TestClient(create_app(_config(rate_limit_per_minute=1)))
    for _ in range(10):
        resp = client.get("/health")
        assert resp.status_code == 200


# --- upload size / MIME sniffing ----------------------------------------------------


def test_configurable_upload_limit_rejects_oversized_file():
    client = TestClient(create_app(_config(rate_limit_per_minute=1000, max_upload_mb=1)))
    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024)
    resp = client.post("/api/inspect/file", files={"file": ("big.png", oversized, "image/png")})
    assert resp.status_code == 413


def test_mime_sniff_rejects_mismatched_content():
    client = TestClient(create_app(_config(rate_limit_per_minute=1000)))
    fake_png = b"this is not a real png file at all, just plain text pretending to be one"
    resp = client.post("/api/inspect/file", files={"file": ("fake.png", fake_png, "image/png")})
    assert resp.status_code == 400


def test_mime_sniff_accepts_genuine_content():
    assert sniff_mime_matches_extension(b"%PDF-1.7\n...", ".pdf") is True
    assert sniff_mime_matches_extension(b"\x89PNG\r\n\x1a\nrest", ".png") is True
    assert sniff_mime_matches_extension(b"not a pdf", ".pdf") is False
    assert sniff_mime_matches_extension(b"whatever plain text", ".txt") is True  # not sniffed


# --- generic error responses --------------------------------------------------------


def test_unsupported_extension_returns_generic_json_not_traceback():
    client = TestClient(create_app(_config(rate_limit_per_minute=1000)))
    resp = client.post("/api/inspect/file", files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    assert resp.status_code == 400
    body = resp.json()
    assert "detail" in body
    assert "Traceback" not in resp.text
    assert "site-packages" not in resp.text


# --- concurrency / timeout runner ----------------------------------------------------


def test_bounded_runner_rejects_when_saturated():
    import threading

    runner = BoundedRunner(max_concurrent=1, timeout_seconds=5)
    release = threading.Event()

    def slow():
        release.wait(2)
        return "done"

    t = threading.Thread(target=lambda: runner.run(slow))
    t.start()
    try:
        import time

        time.sleep(0.1)  # let the first job acquire the semaphore
        try:
            runner.run(lambda: "should not run")
            raised = False
        except ServerBusyError:
            raised = True
        assert raised
    finally:
        release.set()
        t.join(timeout=3)
        runner.shutdown()


def test_bounded_runner_times_out_long_jobs():
    import time

    runner = BoundedRunner(max_concurrent=2, timeout_seconds=1)
    try:
        raised = False
        try:
            runner.run(lambda: time.sleep(5))
        except ProcessingTimeoutError:
            raised = True
        assert raised
    finally:
        runner.shutdown()
