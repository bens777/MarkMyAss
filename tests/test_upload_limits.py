"""Per-format upload limits + trusted-proxy rate-limit hardening.

Production load testing (2026-08) showed large TEXT cleaning is CPU-bound
(~5s/MB): >~3MB text blows the 30s processing timeout, and the timed-out
job keeps running as an unkillable worker thread. These tests pin the
mitigation: text formats are capped at 2 MB server-side BEFORE any
processing, while binary formats keep the global limit; and per-IP rate
limiting keys on the only part of X-Forwarded-For a client cannot forge.
"""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.security import MAX_TEXT_UPLOAD_BYTES, MAX_TEXT_UPLOAD_MB, TEXT_LIMIT_MESSAGE
from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig


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


def _txt(n_bytes: int) -> bytes:
    return (b"clean ascii text with no hidden marks \n" * (n_bytes // 39 + 1))[:n_bytes]


def _noise_png(side: int) -> bytes:
    """A genuinely valid PNG made of random noise -- barely compressible,
    so a few megapixels yields a multi-MB file."""

    img = Image.frombytes("RGB", (side, side), os.urandom(side * side * 3))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# --- Text cap: enforced server-side, before processing -----------------------------------


def test_text_at_exactly_2mb_is_accepted(client):
    data = _txt(MAX_TEXT_UPLOAD_BYTES)
    r = client.post("/api/inspect/file", files={"file": ("big.txt", data)})
    assert r.status_code == 200
    assert "session_id" in r.json()


def test_text_just_over_2mb_is_rejected_with_413_before_processing(client, monkeypatch):
    import ghostmark.web.app as app_module

    def _must_not_run(*a, **k):  # pragma: no cover - failing is the point
        raise AssertionError("processing ran for a rejected oversize text file")

    monkeypatch.setattr(app_module, "inspect_file", _must_not_run)
    data = _txt(MAX_TEXT_UPLOAD_BYTES + 1024)
    r = client.post("/api/inspect/file", files={"file": ("big.txt", data)})
    assert r.status_code == 413
    assert r.json()["detail"] == TEXT_LIMIT_MESSAGE
    assert f"Text files are currently limited to {MAX_TEXT_UPLOAD_MB} MB." == TEXT_LIMIT_MESSAGE


def test_5mb_text_never_enters_processing_and_leaves_no_work_behind(client, monkeypatch):
    import ghostmark.web.app as app_module

    calls = []
    monkeypatch.setattr(app_module, "inspect_file", lambda *a, **k: calls.append(1))
    r = client.post("/api/inspect/file", files={"file": ("huge.txt", _txt(5 * 1024 * 1024))})
    assert r.status_code == 413
    assert calls == []  # nothing was ever submitted to the worker pool
    # And no orphaned session/temp dir was created for the rejected upload.
    assert client.app.state.store._sessions == {}


@pytest.mark.parametrize("name", ["big.md", "big.json", "big.csv"])
def test_all_text_extensions_share_the_cap(client, name):
    r = client.post("/api/inspect/file", files={"file": (name, _txt(3 * 1024 * 1024))})
    assert r.status_code == 413
    assert r.json()["detail"] == TEXT_LIMIT_MESSAGE


def test_pasted_text_over_2mb_rejected_before_processing(client, monkeypatch):
    import ghostmark.web.app as app_module

    monkeypatch.setattr(
        app_module,
        "inspect_text",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("processing ran")),
    )
    r = client.post("/api/inspect/text", json={"text": "x" * (MAX_TEXT_UPLOAD_BYTES + 10)})
    assert r.status_code == 413
    assert "limited to 2 MB" in r.json()["detail"]
    assert client.app.state.store._sessions == {}


# --- Binary formats keep the global 10 MB limit ------------------------------------------


def test_multi_mb_png_still_accepted_under_global_limit(client):
    png = _noise_png(1100)  # ~3.5MB of noise -- well over the text cap
    assert len(png) > MAX_TEXT_UPLOAD_BYTES
    r = client.post("/api/inspect/file", files={"file": ("noise.png", png)})
    assert r.status_code == 200


def test_binary_over_global_limit_rejected_with_global_message(client):
    png = _noise_png(2100)  # ~13MB of noise -- over the 10MB global limit
    assert len(png) > 10 * 1024 * 1024
    r = client.post("/api/inspect/file", files={"file": ("noise.png", png)})
    assert r.status_code == 413
    assert "10 MB" in r.json()["detail"]
    assert r.json()["detail"] != TEXT_LIMIT_MESSAGE


# --- Frontend limits cannot drift --------------------------------------------------------


def test_api_config_exposes_both_limits(client):
    cfg = client.get("/api/config").json()
    assert cfg["max_upload_mb"] == 10
    assert cfg["max_text_upload_mb"] == MAX_TEXT_UPLOAD_MB == 2


def test_frontend_limit_copy_is_config_driven():
    from pathlib import Path

    app_js = (Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "Images & PDFs: up to ${config.max_upload_mb} MB" in app_js
    assert "Text files: up to ${config.max_text_upload_mb} MB" in app_js


# --- X-Forwarded-For: spoofing must not bypass per-IP rate limiting ----------------------


def _tiny_text_post(client, xff):
    return client.post(
        "/api/inspect/text", json={"text": "hi"}, headers={"X-Forwarded-For": xff}
    )


def test_spoofed_first_xff_entry_cannot_bypass_rate_limit():
    client = TestClient(create_app(_config(rate_limit_per_minute=2)))
    # A real client behind one trusted proxy shows up as "<spoof>, <real>":
    # only the RIGHTMOST address is proxy-observed. Varying the spoofed
    # first entry must not grant fresh quota.
    assert _tiny_text_post(client, "1.1.1.1, 9.9.9.9").status_code == 200
    assert _tiny_text_post(client, "2.2.2.2, 9.9.9.9").status_code == 200
    r = _tiny_text_post(client, "3.3.3.3, 9.9.9.9")
    assert r.status_code == 429


def test_legitimate_forwarded_client_ips_get_separate_budgets():
    client = TestClient(create_app(_config(rate_limit_per_minute=2)))
    assert _tiny_text_post(client, "203.0.113.10").status_code == 200
    assert _tiny_text_post(client, "203.0.113.10").status_code == 200
    assert _tiny_text_post(client, "203.0.113.10").status_code == 429  # own quota exhausted
    # A different real client (different proxy-observed address) is unaffected.
    assert _tiny_text_post(client, "203.0.113.20").status_code == 200
