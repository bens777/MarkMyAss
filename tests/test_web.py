"""Web UI: routes, session lifecycle, upload safety, temp file cleanup."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.web.app import create_app

ZWSP = chr(0x200B)


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["local_only"] is True


def test_index_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "GhostMark" in resp.text


def test_inspect_clean_verify_text_flow(client):
    resp = client.post("/api/inspect/text", json={"text": f"hidden{ZWSP}text"})
    assert resp.status_code == 200
    body = resp.json()
    session_id = body["session_id"]
    assert any(d["detector"] == "unicode" and d["status"] == "found" for d in body["report"]["detections"])

    clean_resp = client.post(f"/api/clean/{session_id}")
    assert clean_resp.status_code == 200
    assert clean_resp.json()["cleaned_text"] == "hiddentext"

    verify_resp = client.post(f"/api/verify/{session_id}")
    assert verify_resp.status_code == 200
    verify_body = verify_resp.json()
    assert "unicode" in verify_body["resolved"]


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def test_inspect_clean_verify_download_file_flow(client):
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png_bytes(), "image/png")})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    clean_resp = client.post(f"/api/clean/{session_id}")
    assert clean_resp.status_code == 200

    verify_resp = client.post(f"/api/verify/{session_id}")
    assert verify_resp.status_code == 200

    download_resp = client.get(f"/api/download/{session_id}")
    assert download_resp.status_code == 200
    assert "photo.ghostmark.png" in download_resp.headers["content-disposition"]


def test_download_before_clean_returns_400(client):
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png_bytes(), "image/png")})
    session_id = resp.json()["session_id"]
    download_resp = client.get(f"/api/download/{session_id}")
    assert download_resp.status_code == 400


def test_unsupported_extension_rejected(client):
    resp = client.post("/api/inspect/file", files={"file": ("virus.exe", b"MZ\x00\x00", "application/octet-stream")})
    assert resp.status_code == 400


def test_path_traversal_filename_is_sanitized(client):
    resp = client.post(
        "/api/inspect/file", files={"file": ("../../../../etc/passwd.txt", b"hello", "text/plain")}
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    clean_resp = client.post(f"/api/clean/{session_id}")
    assert clean_resp.status_code == 200


def test_unknown_session_returns_404(client):
    resp = client.post("/api/clean/does-not-exist")
    assert resp.status_code == 404


def test_verify_without_clean_returns_400(client):
    resp = client.post("/api/inspect/text", json={"text": "hello"})
    session_id = resp.json()["session_id"]
    verify_resp = client.post(f"/api/verify/{session_id}")
    assert verify_resp.status_code == 400


def test_session_delete_cleans_up_temp_dir(client):
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png_bytes(), "image/png")})
    session_id = resp.json()["session_id"]

    del_resp = client.delete(f"/api/session/{session_id}")
    assert del_resp.status_code == 200

    # A cleaned-up session must be gone -- subsequent calls 404.
    clean_resp = client.post(f"/api/clean/{session_id}")
    assert clean_resp.status_code == 404
