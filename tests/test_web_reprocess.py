"""Web API tests for the Deep Reprocess endpoint."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.web.app import create_app


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def _png_bytes(size=(140, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 60, 60)).save(buf, format="PNG")
    return buf.getvalue()


def _upload_image(client) -> str:
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png_bytes(), "image/png")})
    assert resp.status_code == 200
    return resp.json()["session_id"]


def test_config_exposes_reprocess_profiles(client):
    profiles = client.get("/api/config").json()["reprocess_profiles"]
    assert {p["name"] for p in profiles} == {"light", "medium", "strong"}
    assert all("estimated_compute_cost" in p for p in profiles)


def test_reprocess_returns_three_separate_categories(client):
    sid = _upload_image(client)
    resp = client.post(f"/api/reprocess/{sid}?profile=medium")
    assert resp.status_code == 200
    body = resp.json()

    # the three categories are present and NOT mixed together
    assert "file_level" in body and "detections" in body["file_level"]
    assert "pixel_level" in body and "metrics" in body["pixel_level"]
    assert body["statistical"]["locally_verifiable"] is False
    assert "SynthID" in body["statistical"]["note"]

    m = body["metrics"]
    assert m["output_dimensions"] == [140, 100]
    assert 0.0 <= m["ssim"] <= 1.0
    assert body["download_available"] is True
    # raw output bytes must NOT be shipped in the JSON payload
    assert "output_bytes" not in body


def test_reprocess_download_variant(client):
    sid = _upload_image(client)
    client.post(f"/api/reprocess/{sid}?profile=light")
    resp = client.get(f"/api/download/{sid}?variant=reprocess")
    assert resp.status_code == 200
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"  # a real PNG comes back
    assert "reprocessed" in resp.headers.get("content-disposition", "")


def test_reprocess_format_override(client):
    sid = _upload_image(client)
    body = client.post(f"/api/reprocess/{sid}?profile=light&out_format=webp").json()
    assert body["output_format"] == "WEBP"
    assert body["output_suffix"] == ".webp"


def test_reprocess_rejects_bad_profile_and_missing_session(client):
    sid = _upload_image(client)
    assert client.post(f"/api/reprocess/{sid}?profile=bogus").status_code == 400
    assert client.post("/api/reprocess/does-not-exist?profile=light").status_code == 404


def test_reprocess_rejects_non_image_session(client):
    r = client.post("/api/inspect/file", files={"file": ("notes.txt", b"plain text", "text/plain")})
    sid = r.json()["session_id"]
    assert client.post(f"/api/reprocess/{sid}?profile=light").status_code == 400
