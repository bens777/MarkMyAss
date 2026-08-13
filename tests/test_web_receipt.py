"""Web UI: Verification Receipt endpoints (JSON display + JSON/HTML/TXT download)."""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.web.app import create_app

ZWSP = chr(0x200B)


@pytest.fixture()
def client():
    with TestClient(create_app()) as c:
        yield c


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _file_session(client) -> str:
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png_bytes(), "image/png")})
    session_id = resp.json()["session_id"]
    client.post(f"/api/clean/{session_id}")
    client.post(f"/api/verify/{session_id}")
    return session_id


def _text_session(client) -> str:
    resp = client.post("/api/inspect/text", json={"text": f"hidden{ZWSP}text"})
    session_id = resp.json()["session_id"]
    client.post(f"/api/clean/{session_id}")
    client.post(f"/api/verify/{session_id}")
    return session_id


def test_receipt_json_display_endpoint(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ghostmark_verification_receipt"] is True
    assert body["file"] == "photo.ghostmark.png"
    assert "sha256_original" in body
    assert "sha256_cleaned" in body
    assert "verdict" in body


def test_receipt_requires_verify_first(client):
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png_bytes(), "image/png")})
    session_id = resp.json()["session_id"]
    client.post(f"/api/clean/{session_id}")
    # No verify call yet.
    receipt_resp = client.get(f"/api/receipt/{session_id}")
    assert receipt_resp.status_code == 400


def test_receipt_download_json(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}/download?format=json")
    assert resp.status_code == 200
    assert "attachment;" in resp.headers["content-disposition"]
    assert ".ghostmark-receipt.json" in resp.headers["content-disposition"]
    payload = json.loads(resp.text)
    assert payload["ghostmark_verification_receipt"] is True


def test_receipt_download_html(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}/download?format=html")
    assert resp.status_code == 200
    assert ".ghostmark-receipt.html" in resp.headers["content-disposition"]
    assert resp.text.strip().startswith("<!doctype html>")


def test_receipt_download_txt(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}/download?format=txt")
    assert resp.status_code == 200
    assert ".ghostmark-receipt.txt" in resp.headers["content-disposition"]
    assert "GHOSTMARK VERIFICATION RECEIPT" in resp.text


def test_receipt_download_rejects_unknown_format(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}/download?format=exe")
    assert resp.status_code == 422  # FastAPI query-param pattern validation


def test_receipt_defaults_to_json_format(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}/download")
    assert resp.status_code == 200
    assert ".ghostmark-receipt.json" in resp.headers["content-disposition"]


def test_receipt_works_for_text_sessions(client):
    session_id = _text_session(client)
    resp = client.get(f"/api/receipt/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["file"] == "pasted-text"
    assert body["sha256_original"]
    assert body["sha256_cleaned"]


def test_receipt_never_claims_statistical_watermark_verified_over_http(client):
    session_id = _file_session(client)
    resp = client.get(f"/api/receipt/{session_id}")
    body = resp.json()
    assert all(v == "unverified" for v in body["statistical_watermark_status"].values())


def test_cleaned_file_and_receipt_both_downloadable_same_session(client):
    """The exact flow the product spec requires: download the cleaned file
    AND the verification receipt from the same completed session."""

    session_id = _file_session(client)

    file_resp = client.get(f"/api/download/{session_id}")
    assert file_resp.status_code == 200

    receipt_resp = client.get(f"/api/receipt/{session_id}/download?format=json")
    assert receipt_resp.status_code == 200

    # Order independence: receipt first should also work in a fresh session.
    session_id_2 = _file_session(client)
    receipt_resp_2 = client.get(f"/api/receipt/{session_id_2}/download?format=json")
    assert receipt_resp_2.status_code == 200
    file_resp_2 = client.get(f"/api/download/{session_id_2}")
    assert file_resp_2.status_code == 200
