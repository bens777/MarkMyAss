"""Paid batch lot (ghostmark.web.batch): payment verification, one payment =
one finalized lot, retries before finalization, ZIP download, and -- above
all -- that the free single-file tool is unchanged whether the flag is on
or off. The per-file pipeline decisions are covered in
tests/test_batch_pipeline.py; here the real cleaners/verifiers run."""

from __future__ import annotations

import io
import json
import re
import sqlite3
import threading
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.web import batch as batch_module
from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig

CS = "cs_test_abc123"
PRICE_CENTS = 199


def _session(session_id=CS, **overrides):
    s = {
        "id": session_id,
        "mode": "payment",
        "payment_status": "paid",
        "amount_total": PRICE_CENTS,
        "currency": "eur",
        "metadata": {"markmyass": "batch"},
    }
    s.update(overrides)
    return s


class FakeGateway:
    """Stands in for Stripe: serves whatever sessions the test registers."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {CS: _session()}
        self.checkouts = 0

    def create_checkout_session(self, *, success_url, cancel_url, locale):
        self.checkouts += 1
        assert "{CHECKOUT_SESSION_ID}" in success_url
        return "https://checkout.stripe.test/session"

    def retrieve_session(self, session_id):
        return self.sessions.get(session_id)


def _config(tmp_path, *, enabled=True, mode="hosted") -> WebConfig:
    return WebConfig(
        mode=mode,
        base_path="/",
        public_url="https://markmyass.test",
        session_ttl_seconds=600,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=10,
        stats_db_path=str(tmp_path / "stats.db"),
        batch_enabled=enabled,
        commerce_db_path=str(tmp_path / "commerce.db"),
        batch_price_cents=PRICE_CENTS,
        batch_max_files=50,
    )


@pytest.fixture()
def env(tmp_path, monkeypatch):
    # Lot workdirs go under the OS temp dir; isolate them per test.
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    gateway = FakeGateway()
    app = create_app(_config(tmp_path), batch_gateway=gateway)
    with TestClient(app) as client:
        yield client, gateway, tmp_path / "commerce.db"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(9, 8, 7)).save(buf, format="PNG")
    return buf.getvalue()


def _hdr(session_id=CS):
    return {"X-Batch-Session": session_id}


def _verify(client, session_id=CS):
    return client.post("/api/batch/verify", json={"session_id": session_id})


def _upload(client, name, data, mime="image/png", session_id=CS):
    return client.post("/api/batch/files", headers=_hdr(session_id), files={"file": (name, data, mime)})


def _process(client, name, data, mime="image/png"):
    """Drive one file through the whole pipeline like batch.js does; return the final response."""

    resp = _upload(client, name, data, mime)
    if resp.status_code != 200:
        return resp
    key = resp.json()["key"]
    resp = client.post(f"/api/batch/files/{key}/verify", headers=_hdr())
    if resp.status_code == 200 and resp.json()["stage"] == "needs_deep_clean":
        resp = client.post(f"/api/batch/files/{key}/deep-clean", headers=_hdr())
        if resp.status_code != 200:
            return resp
        resp = client.post(f"/api/batch/files/{key}/verify", headers=_hdr())
    return resp


def _status(db, session_id=CS):
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT status FROM batch_payments WHERE stripe_session_id = ?", (session_id,)).fetchone()
    return row[0] if row else None


def _count(db) -> int:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COUNT(*) FROM batch_payments").fetchone()[0]


# --- checkout limits --------------------------------------------------------------------


def test_fewer_than_two_files_is_refused_at_checkout(env):
    client, gateway, _ = env
    for n in (0, 1):
        resp = client.post("/api/batch/checkout", json={"file_count": n})
        assert resp.status_code == 400, n
    assert gateway.checkouts == 0


def test_more_than_fifty_files_is_refused_at_checkout(env):
    client, gateway, _ = env
    assert client.post("/api/batch/checkout", json={"file_count": 51}).status_code == 400
    assert client.post("/api/batch/checkout", json={"file_count": 2, "total_bytes": 65 * 1024 * 1024}).status_code == 400
    assert gateway.checkouts == 0
    resp = client.post("/api/batch/checkout", json={"file_count": 50, "total_bytes": 1024})
    assert resp.status_code == 200 and resp.json()["url"].startswith("https://checkout.stripe.test/")
    # The page itself sends no selection (files are chosen after payment).
    assert client.post("/api/batch/checkout", json={"locale": "fr"}).status_code == 200
    assert gateway.checkouts == 2


# --- payment verification ---------------------------------------------------------------


def test_unpaid_or_unknown_session_is_refused(env):
    client, gateway, db = env
    gateway.sessions["cs_unpaid"] = _session("cs_unpaid", payment_status="unpaid")
    assert _verify(client, "cs_unpaid").status_code == 402
    assert _verify(client, "cs_does_not_exist").status_code == 402
    assert _verify(client, "not-a-session").status_code == 400
    assert _count(db) == 0
    # Nothing can be processed without a verified payment.
    assert _upload(client, "a.png", _png(), session_id="cs_unpaid").status_code == 402
    assert client.post("/api/batch/finalize", headers=_hdr("cs_unpaid")).status_code == 402


def test_wrong_price_currency_or_offer_is_refused(env):
    client, gateway, db = env
    gateway.sessions["cs_cheap"] = _session("cs_cheap", amount_total=99)
    gateway.sessions["cs_usd"] = _session("cs_usd", currency="usd")
    gateway.sessions["cs_other"] = _session("cs_other", metadata={})
    gateway.sessions["cs_sub"] = _session("cs_sub", mode="subscription")
    assert _verify(client, "cs_cheap").status_code == 409
    assert _verify(client, "cs_usd").status_code == 409
    assert _verify(client, "cs_other").status_code == 409
    assert _verify(client, "cs_sub").status_code == 402
    assert _count(db) == 0


def test_valid_paid_session_opens_a_lot(env):
    client, _, db = env
    resp = _verify(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "paid" and body["results"] == [] and body["min_files"] == 2 and body["max_files"] == 50
    assert _status(db) == "paid" and _count(db) == 1
    with sqlite3.connect(db) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(batch_payments)")}
        assert cols == {"id", "stripe_session_id", "status", "created_at", "finalized_at"}
        assert [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ["batch_payments"]


def test_concurrent_verifications_cannot_open_two_lots(env):
    client, _, db = env
    results: list[int] = []

    def worker():
        results.append(_verify(client).status_code)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert results == [200] * 20
    assert _count(db) == 1


# --- processing -------------------------------------------------------------------------


def test_unsupported_files_are_refused_without_spending_the_payment(env):
    client, _, db = env
    assert _verify(client).status_code == 200
    assert _upload(client, "notes.txt", b"hello", "text/plain").status_code == 400
    assert _upload(client, "doc.docx", b"PK\x03\x04", "application/octet-stream").status_code == 400
    assert _upload(client, "fake.png", b"not a png").status_code == 400
    assert _status(db) == "paid"
    # ...and the same payment still works for real files afterwards.
    resp = _process(client, "a.png", _png())
    assert resp.status_code == 200 and resp.json()["stage"] == "done"
    assert _status(db) == "processing"


def test_failed_processing_or_zip_can_be_retried(env, monkeypatch):
    client, _, db = env
    assert _verify(client).status_code == 200
    # A corrupt PDF passes the magic-byte sniff then fails inside pikepdf.
    resp = _process(client, "broken.pdf", b"%PDF-1.4 not a pdf", "application/pdf")
    assert resp.status_code == 400 and "retry" in resp.json()["detail"]
    assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 409  # nothing to zip yet
    assert _status(db) == "paid"
    assert _verify(client).json()["results"] == []  # a failed file is never listed as a result

    assert _process(client, "a.png", _png()).status_code == 200
    assert _process(client, "b.png", _png()).status_code == 200

    # ZIP build blows up -> nothing spent, results kept, retry allowed.
    monkeypatch.setattr(batch_module.zipfile, "ZipFile", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 500
    assert _status(db) == "processing"
    assert [r["name"] for r in _verify(client).json()["results"]] == ["a.png", "b.png"]
    monkeypatch.undo()

    resp = client.post("/api/batch/finalize", headers=_hdr())
    assert resp.status_code == 200 and resp.json()["results"] == 2
    assert _status(db) == "finalized"


def test_successful_zip_finalizes_the_payment_and_contains_results(env):
    client, _, db = env
    assert _verify(client).status_code == 200
    before = client.get("/api/public-stats").json()["files_cleaned_total"]
    statuses = {}
    for name in ("one.png", "two.png", "one.png"):  # duplicate name must not collide
        resp = _process(client, name, _png())
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["stage"] == "done" and body["status"] in ("verified", "incomplete")
        assert body["download_name"] == name.replace(".png", ".ghostmark.png")
        statuses[name] = body["status"]
    assert client.get("/api/public-stats").json()["files_cleaned_total"] == before + 3

    resp = client.post("/api/batch/finalize", headers=_hdr())
    assert resp.status_code == 200
    assert resp.json()["verified"] + resp.json()["incomplete"] == 3
    assert _status(db) == "finalized"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT finalized_at FROM batch_payments").fetchone()[0] is not None

    zip_resp = client.get("/api/batch/zip", headers=_hdr())
    assert zip_resp.status_code == 200 and zip_resp.headers["content-type"].startswith("application/zip")
    tag = ".ghostmark" if statuses["one.png"] == "verified" else ".ghostmark-incomplete"
    with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
        names = set(zf.namelist())
        assert {f"one{tag}.png", f"two{tag}.png", f"one (2){tag}.png", "SUMMARY.txt"} <= names
        assert f"one{tag}-receipt.json" in names
        receipt = json.loads(zf.read(f"one{tag}-receipt.json"))
        assert receipt["ghostmark_verification_receipt"] is True and receipt["file"] == "one.ghostmark.png"
        assert receipt["batch"]["status"] == statuses["one.png"] and receipt["batch"]["deep_clean_used"] is False
        summary = zf.read("SUMMARY.txt").decode()
        assert "/tmp" not in summary and statuses["one.png"].upper() in summary and "deep clean: no" in summary
    # Individual results are gone once zipped; the ZIP is still served.
    workdir = Path(client.app.state.batch._tmp) / "ghostmark-batch-1"
    assert sorted(p.suffix for p in workdir.iterdir()) == [".zip"]
    assert client.get("/api/batch/zip", headers=_hdr()).status_code == 200


def test_finalized_session_cannot_be_used_again(env):
    client, _, db = env
    assert _verify(client).status_code == 200
    assert _process(client, "a.png", _png()).status_code == 200
    assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 200

    resp = _upload(client, "b.png", _png())
    assert resp.status_code == 409 and "already been used" in resp.json()["detail"]
    resp = _verify(client)
    assert resp.status_code == 409 and "already been used" in resp.json()["detail"]
    again = client.post("/api/batch/finalize", headers=_hdr())
    assert again.status_code == 200 and again.json()["status"] == "finalized"  # idempotent, no second lot
    assert _status(db) == "finalized" and _count(db) == 1

    # After the ZIP expires the payment stays spent.
    client.app.state.batch.sweep(now=__import__("time").time() + 3601)
    assert client.get("/api/batch/zip", headers=_hdr()).status_code == 404
    assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 410


def test_incomplete_result_can_be_removed_and_replaced_before_finalizing(env):
    client, _, _ = env
    assert _verify(client).status_code == 200
    first = _process(client, "a.png", _png()).json()
    assert first["stage"] == "done"
    assert client.delete(f"/api/batch/files/{first['key']}", headers=_hdr()).status_code == 200
    assert _verify(client).json()["results"] == []
    assert client.delete(f"/api/batch/files/{first['key']}", headers=_hdr()).status_code == 404
    assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 409  # nothing left to zip
    assert _process(client, "replacement.png", _png()).status_code == 200
    assert [r["name"] for r in _verify(client).json()["results"]] == ["replacement.png"]


def test_stripe_session_id_never_reaches_the_logs(env, caplog):
    client, _, _ = env
    with caplog.at_level("DEBUG"):
        assert _verify(client).status_code == 200
        _process(client, "a.png", _png())
        _process(client, "bad.pdf", b"%PDF-1.4 x", "application/pdf")
        client.post("/api/batch/finalize", headers=_hdr())
    assert "cs_" not in caplog.text


# --- the free tool is unchanged ---------------------------------------------------------


def test_free_single_file_flow_unchanged_with_feature_on(env):
    client, _, _ = env
    resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png(), "image/png")})
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    assert client.post(f"/api/clean/{sid}").status_code == 200
    assert client.post(f"/api/verify/{sid}").status_code == 200
    assert client.get(f"/api/download/{sid}").status_code == 200
    assert client.get("/api/config").json()["batch_enabled"] is True
    page = client.get("/batch")
    assert page.status_code == 200 and "noindex" in page.text
    # No file picker before payment; the only picker belongs to the paid lot view.
    assert "buy-input" not in page.text and 'id="lot-input"' in page.text
    assert "select your files again" not in page.text.lower()
    assert "/batch" not in client.get("/sitemap.xml").text
    offer = client.get("/api/batch/offer").json()
    assert offer == {"price_cents": 199, "currency": "eur", "min_files": 2, "max_files": 50, "max_upload_mb": 10, "max_total_mb": 64}


def test_feature_off_by_default_exposes_nothing(tmp_path):
    with TestClient(create_app(_config(tmp_path, enabled=False))) as client:
        assert client.get("/api/config").json()["batch_enabled"] is False
        assert client.get("/batch").status_code == 404
        assert client.post("/api/batch/verify", json={"session_id": CS}).status_code == 404
        assert not (tmp_path / "commerce.db").exists()
        resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png(), "image/png")})
        assert resp.status_code == 200


def test_flag_on_in_local_mode_stays_off(tmp_path):
    with TestClient(create_app(_config(tmp_path, mode="local"), batch_gateway=FakeGateway())) as client:
        assert client.get("/api/config").json()["batch_enabled"] is False
        assert client.get("/batch").status_code == 404


def test_api_config_never_leaks_the_stripe_key(tmp_path):
    cfg = WebConfig(
        mode="hosted", base_path="/", public_url="https://markmyass.test", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
        stats_db_path=str(tmp_path / "s.db"), batch_enabled=True, commerce_db_path=str(tmp_path / "c.db"),
        stripe_secret_key="sk_test_SECRET", stripe_price_id="price_1",
    )
    with TestClient(create_app(cfg, batch_gateway=FakeGateway())) as client:
        text = client.get("/api/config").text + client.get("/api/batch/offer").text + client.get("/batch").text
        assert "SECRET" not in text and "sk_test" not in text and "price_1" not in text


def test_no_leftover_of_the_previous_credit_pack_design():
    """No e-mail, token, credit, Resend or 30-day validity anywhere in the
    feature's code, config, docs, tests or UI texts."""

    root = Path(__file__).resolve().parents[1]
    files = [
        root / "src/ghostmark/web/batch.py",
        root / "src/ghostmark/web/config.py",
        root / "src/ghostmark/web/app.py",
        root / "src/ghostmark/web/static/batch.html",
        root / "src/ghostmark/web/static/batch.js",
        root / "src/ghostmark/web/static/index.html",
        root / "src/ghostmark/web/static/i18n-fr.js",
        root / "pyproject.toml",
        root / "constraints.txt",
        root / ".env.example",
        root / "PRIVACY.md",
        root / "CHANGELOG.md",
        Path(__file__),
    ]
    forbidden = re.compile(
        r"resend|mailer|mail_from|magic.?link|token_hash|TOKEN_SECRET|mma_|credits?_remaining|"
        r"batch_credits|expires_at|validity_days|30.?(days|jours)|50 cr[eé]dits|webhook",
        re.IGNORECASE,
    )
    for f in files:
        text = f.read_text(encoding="utf-8")
        if f == Path(__file__):
            text = text.split("def test_no_leftover_of_the_previous_credit_pack_design")[0]
        hits = sorted({m.group(0) for m in forbidden.finditer(text)})
        assert not hits, f"{f.name}: {hits}"
