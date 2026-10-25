"""The 24-hour window of the paid batch lot (ghostmark.web.batch).

Rule under test: after a Stripe-confirmed payment the customer has 24 hours,
counted from the Checkout Session's own `created` time, to process and
finalize the single lot the payment buys; the same session_id URL is the way
back to it. Past the window every lot route answers HTTP 410. Once the ZIP
is built it is downloadable for one hour from its creation, then 410. A
finalized lot is never reopened, a restart that wipes the temp files never
loses the payment, and existing databases migrate in place.

Time is injected through BatchFeature's server clock (`_now`); nothing the
browser sends is ever a date."""

from __future__ import annotations

import io
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.web import batch as batch_module
from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "ghostmark" / "web" / "static"

CS = "cs_test_window"
PRICE_CENTS = 199
PAID_AT = 1_800_000_000  # Stripe `created` (unix seconds) of the test session
HOUR = 3600
DAY = 24 * HOUR
FR_EXPIRED = "Ce paiement a expiré. Le lot devait être traité dans les 24 heures suivant le paiement."
EN_EXPIRED = "This payment has expired. The lot had to be processed within 24 hours of payment."
FR_WINDOW = "Vous avez 24 heures après le paiement pour terminer ce lot."
EN_WINDOW = "You have 24 hours after payment to complete this batch."


def _session(session_id=CS, **overrides):
    s = {
        "id": session_id,
        "mode": "payment",
        "payment_status": "paid",
        "amount_total": PRICE_CENTS,
        "currency": "eur",
        "metadata": {"markmyass": "batch"},
        "created": PAID_AT,
    }
    s.update(overrides)
    return s


class FakeGateway:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {CS: _session()}

    def create_checkout_session(self, **kwargs):
        return "https://checkout.stripe.test/session"

    def retrieve_session(self, session_id):
        return self.sessions.get(session_id)


def _config(tmp_path) -> WebConfig:
    return WebConfig(
        mode="hosted", base_path="/", public_url="https://markmyass.test", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
        stats_db_path=str(tmp_path / "stats.db"), batch_enabled=True, commerce_db_path=str(tmp_path / "commerce.db"),
        batch_price_cents=PRICE_CENTS, batch_max_files=50,
    )


class Clock:
    """The server clock, settable by the test (absolute, never from the browser)."""

    def __init__(self, now: float) -> None:
        self.now = float(now)

    def __call__(self) -> float:
        return self.now


@pytest.fixture()
def tmp(tmp_path, monkeypatch):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    return tmp_path


def _start(tmp, gateway=None, now: float = PAID_AT + 60):
    """A fresh app process on the same commerce DB; returns (client, clock)."""

    app = create_app(_config(tmp), batch_gateway=gateway or FakeGateway())
    client = TestClient(app)
    client.__enter__()
    clock = Clock(now)
    client.app.state.batch._now = clock
    return client, clock


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _hdr(session_id=CS):
    return {"X-Batch-Session": session_id}


def _verify(client, session_id=CS):
    return client.post("/api/batch/verify", json={"session_id": session_id})


def _process(client, name, session_id=CS):
    resp = client.post("/api/batch/files", headers=_hdr(session_id), files={"file": (name, _png(), "image/png")})
    if resp.status_code != 200:
        return resp
    key = resp.json()["key"]
    resp = client.post(f"/api/batch/files/{key}/verify", headers=_hdr(session_id))
    if resp.status_code == 200 and resp.json()["stage"] == "needs_deep_clean":
        client.post(f"/api/batch/files/{key}/deep-clean", headers=_hdr(session_id))
        resp = client.post(f"/api/batch/files/{key}/verify", headers=_hdr(session_id))
    return resp


def _row(tmp, session_id=CS):
    with sqlite3.connect(tmp / "commerce.db") as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM batch_payments WHERE stripe_session_id = ?", (session_id,)).fetchone()


def _expired(resp):
    return resp.status_code == 410 and resp.headers["x-batch-error"] == "payment_expired" and resp.json()["detail"] == EN_EXPIRED


# --- the window --------------------------------------------------------------------------------


def test_payment_aged_23h59_is_accepted_end_to_end(tmp):
    client, clock = _start(tmp)
    try:
        clock.now = PAID_AT + DAY - 60  # 23 h 59 after the Stripe payment
        resp = _verify(client)
        assert resp.status_code == 200
        assert resp.json()["window_hours"] == 24 and 0 < resp.json()["seconds_left"] <= 60
        assert _process(client, "a.png").status_code == 200
        assert _process(client, "b.png").status_code == 200
        done = client.post("/api/batch/finalize", headers=_hdr())
        assert done.status_code == 200 and done.json()["results"] == 2
        assert _row(tmp)["status"] == "finalized"
        assert client.get("/api/batch/zip", headers=_hdr()).status_code == 200
    finally:
        client.__exit__(None, None, None)


def test_payment_aged_24h01_is_refused_with_410_everywhere(tmp):
    client, clock = _start(tmp)
    try:
        clock.now = PAID_AT + DAY + 60  # 24 h 01
        resp = _verify(client)
        assert _expired(resp)
        # The payment is recorded (never lost) but nothing can be done with it.
        assert _row(tmp)["status"] == "paid"
        assert _expired(client.post("/api/batch/files", headers=_hdr(), files={"file": ("a.png", _png(), "image/png")}))
        assert _expired(client.post("/api/batch/files/deadbeef/verify", headers=_hdr()))
        assert _expired(client.post("/api/batch/finalize", headers=_hdr()))
        assert _expired(client.get("/api/batch/zip", headers=_hdr()))
        assert _expired(client.delete("/api/batch/files/deadbeef", headers=_hdr()))
    finally:
        client.__exit__(None, None, None)


def test_window_runs_out_mid_lot(tmp):
    client, clock = _start(tmp)
    try:
        clock.now = PAID_AT + DAY - 300
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
        clock.now = PAID_AT + DAY + 1
        assert _expired(_process(client, "b.png"))
        assert _expired(client.post("/api/batch/finalize", headers=_hdr()))
        assert _row(tmp)["status"] == "processing"  # never finalized, never spent
    finally:
        client.__exit__(None, None, None)


def test_expiry_is_measured_from_stripe_created_not_from_first_visit_or_upload(tmp):
    client, clock = _start(tmp)
    try:
        # First visit 20 hours after the Stripe payment: fine.
        clock.now = PAID_AT + 20 * HOUR
        assert _verify(client).status_code == 200
        row = _row(tmp)
        assert row["paid_at"] == PAID_AT and row["created_at"] == PAID_AT + 20 * HOUR
        # First upload at 23 h 30: fine.
        clock.now = PAID_AT + DAY - 30 * 60
        assert _process(client, "a.png").status_code == 200
        # 24 h 01 after the PAYMENT (only 4 hours after the first visit, 31
        # minutes after the first upload): refused.
        clock.now = PAID_AT + DAY + 60
        assert _expired(_verify(client))
        assert _expired(_process(client, "b.png"))
    finally:
        client.__exit__(None, None, None)


def test_a_date_sent_by_the_browser_is_never_used(tmp):
    client, clock = _start(tmp)
    try:
        clock.now = PAID_AT + DAY + 60
        # Extra fields in the body, query or headers cannot move the window.
        resp = client.post(
            "/api/batch/verify?created=9999999999&paid_at=9999999999",
            json={"session_id": CS, "created": 9_999_999_999, "paid_at": 9_999_999_999, "now": 0},
            headers={"X-Batch-Created": "9999999999", "Date": "Thu, 01 Jan 2099 00:00:00 GMT"},
        )
        assert _expired(resp)
        assert _row(tmp)["paid_at"] == PAID_AT
    finally:
        client.__exit__(None, None, None)


def test_stripe_session_without_created_starts_the_window_at_server_time(tmp, caplog):
    gateway = FakeGateway()
    gateway.sessions["cs_nocreated"] = _session("cs_nocreated", created=None)
    client, clock = _start(tmp, gateway, now=5_000_000)
    try:
        with caplog.at_level("WARNING"):
            assert _verify(client, "cs_nocreated").status_code == 200
        assert _row(tmp, "cs_nocreated")["paid_at"] == 5_000_000
        assert "cs_" not in caplog.text
        clock.now = 5_000_000 + DAY + 1
        assert _expired(_verify(client, "cs_nocreated"))
    finally:
        client.__exit__(None, None, None)


# --- coming back ---------------------------------------------------------------------------------


def test_coming_back_with_the_same_session_before_24h_resumes_the_lot(tmp):
    client, clock = _start(tmp)
    try:
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
        assert _process(client, "b.png").status_code == 200
        # Leaves, comes back 20 minutes later with the same URL: results listed, lot still open.
        clock.now += 20 * 60
        resp = _verify(client)
        assert resp.status_code == 200
        assert [r["name"] for r in resp.json()["results"]] == ["a.png", "b.png"]
        assert resp.json()["status"] == "processing"
        # Can add / replace files and finish.
        assert _process(client, "c.png").status_code == 200
        done = client.post("/api/batch/finalize", headers=_hdr())
        assert done.status_code == 200 and done.json()["results"] == 3
    finally:
        client.__exit__(None, None, None)


def test_restart_that_wipes_the_temp_files_lets_the_customer_select_files_again(tmp):
    client, clock = _start(tmp)
    try:
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
        assert _process(client, "b.png").status_code == 200
        workdir = Path(client.app.state.batch._tmp) / "ghostmark-batch-1"
        assert any(workdir.iterdir())
    finally:
        client.__exit__(None, None, None)

    # Container restart: the tmpfs is empty, the SQLite volume is not.
    for p in workdir.iterdir():
        p.unlink()
    workdir.rmdir()
    client, clock = _start(tmp, now=PAID_AT + 10 * HOUR)
    try:
        resp = _verify(client)
        assert resp.status_code == 200
        assert resp.json()["results"] == [] and resp.json()["zip_available"] is False
        assert _row(tmp)["status"] == "processing" and _row(tmp)["paid_at"] == PAID_AT
        # Select the files again and finish: the payment was not lost.
        assert _process(client, "a.png").status_code == 200
        assert _process(client, "b.png").status_code == 200
        done = client.post("/api/batch/finalize", headers=_hdr())
        assert done.status_code == 200 and done.json()["results"] == 2
        assert client.get("/api/batch/zip", headers=_hdr()).status_code == 200
    finally:
        client.__exit__(None, None, None)

    # ...but not past the 24 hours.
    client, clock = _start(tmp, now=PAID_AT + DAY + 1)
    try:
        assert client.get("/api/batch/zip", headers=_hdr()).status_code == 410  # ZIP hour elapsed too
    finally:
        client.__exit__(None, None, None)


def test_restart_with_an_expired_unfinalized_payment(tmp):
    client, _ = _start(tmp)
    try:
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
    finally:
        client.__exit__(None, None, None)
    client, _ = _start(tmp, now=PAID_AT + DAY + 1)
    try:
        assert _expired(_verify(client))
        assert _expired(_process(client, "b.png"))
    finally:
        client.__exit__(None, None, None)


# --- one payment, one finalized lot ------------------------------------------------------------


def test_a_finalized_lot_is_never_reopened(tmp):
    client, clock = _start(tmp)
    try:
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
        assert _process(client, "b.png").status_code == 200
        assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 200
        for when in (clock.now + 1, PAID_AT + DAY - 1, PAID_AT + DAY + 1, PAID_AT + 30 * DAY):
            clock.now = when
            resp = _verify(client)
            assert resp.status_code == 409 and resp.headers["x-batch-error"] == "already_used", when
            resp = _process(client, "c.png")
            assert resp.status_code == 409 and resp.headers["x-batch-error"] == "already_used", when
            again = client.post("/api/batch/finalize", headers=_hdr())
            assert again.status_code in (200, 410) and _row(tmp)["status"] == "finalized"
        workdir = Path(client.app.state.batch._tmp) / "ghostmark-batch-1"
    finally:
        client.__exit__(None, None, None)

    # Even after a restart that wiped the ZIP, within the 24 hours: still spent.
    for p in workdir.iterdir():
        p.unlink()
    client, _ = _start(tmp, now=PAID_AT + 2 * HOUR)
    try:
        resp = _verify(client)
        assert resp.status_code == 409 and resp.headers["x-batch-error"] == "already_used"
        assert _process(client, "c.png").status_code == 409
        resp = client.get("/api/batch/zip", headers=_hdr())
        assert resp.status_code == 410 and resp.headers["x-batch-error"] == "zip_expired"
        assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 410
        with sqlite3.connect(tmp / "commerce.db") as conn:
            assert conn.execute("SELECT COUNT(*) FROM batch_payments").fetchone()[0] == 1
    finally:
        client.__exit__(None, None, None)


# --- the ZIP hour ---------------------------------------------------------------------------------


def test_zip_is_downloadable_until_59m59_and_refused_after_one_hour(tmp):
    client, clock = _start(tmp)
    try:
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
        assert _process(client, "b.png").status_code == 200
        clock.now = PAID_AT + DAY - 1  # finalized at the very end of the window: still fine
        assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 200
        finalized_at = _row(tmp)["finalized_at"]
        assert finalized_at == clock.now

        for offset in (0, 30 * 60, HOUR - 1):  # ...up to 59 min 59 s after creation
            clock.now = finalized_at + offset
            resp = client.get("/api/batch/zip", headers=_hdr())
            assert resp.status_code == 200 and resp.headers["content-type"].startswith("application/zip"), offset
            assert client.post("/api/batch/finalize", headers=_hdr()).json()["status"] == "finalized"

        clock.now = finalized_at + HOUR + 1
        resp = client.get("/api/batch/zip", headers=_hdr())
        assert resp.status_code == 410 and resp.headers["x-batch-error"] == "zip_expired"
        assert client.post("/api/batch/finalize", headers=_hdr()).status_code == 410
        assert _row(tmp)["status"] == "finalized"  # spent for good
        # The sweeper also removes the file itself after the hour.
        client.app.state.batch.sweep(now=__import__("time").time() + HOUR + 1)
        assert client.get("/api/batch/zip", headers=_hdr()).status_code == 410
    finally:
        client.__exit__(None, None, None)


def test_zip_is_not_served_before_finalization(tmp):
    client, _ = _start(tmp)
    try:
        assert _verify(client).status_code == 200
        assert _process(client, "a.png").status_code == 200
        resp = client.get("/api/batch/zip", headers=_hdr())
        assert resp.status_code == 404 and resp.headers["x-batch-error"] == "no_zip"
    finally:
        client.__exit__(None, None, None)


# --- migration ----------------------------------------------------------------------------------


def test_existing_database_is_migrated_in_place_without_losing_payments(tmp):
    db = tmp / "commerce.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE batch_payments ("
            "  id INTEGER PRIMARY KEY,"
            "  stripe_session_id TEXT NOT NULL UNIQUE,"
            "  status TEXT NOT NULL CHECK (status IN ('paid', 'processing', 'finalized')),"
            "  created_at REAL NOT NULL,"
            "  finalized_at REAL)"
        )
        conn.executemany(
            "INSERT INTO batch_payments (stripe_session_id, status, created_at, finalized_at) VALUES (?, ?, ?, ?)",
            [
                ("cs_old_open", "processing", PAID_AT + 600, None),
                ("cs_old_done", "finalized", PAID_AT - 5 * DAY, PAID_AT - 5 * DAY + 900),
            ],
        )
    gateway = FakeGateway()
    gateway.sessions["cs_old_open"] = _session("cs_old_open", created=PAID_AT)
    gateway.sessions["cs_old_done"] = _session("cs_old_done", created=PAID_AT - 5 * DAY)

    client, clock = _start(tmp, gateway, now=PAID_AT + 2 * HOUR)
    try:
        with sqlite3.connect(db) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(batch_payments)")]
            assert cols == ["id", "stripe_session_id", "status", "created_at", "finalized_at", "paid_at"]
            rows = conn.execute("SELECT stripe_session_id, status, created_at, finalized_at, paid_at FROM batch_payments ORDER BY id").fetchall()
        assert rows == [
            ("cs_old_open", "processing", PAID_AT + 600, None, None),
            ("cs_old_done", "finalized", PAID_AT - 5 * DAY, PAID_AT - 5 * DAY + 900, None),
        ]
        # Before any backfill, a pre-migration row's window starts when its
        # lot was opened (never earlier than the payment).
        feature = client.app.state.batch
        assert feature.paid_at(_row(tmp, "cs_old_open")) == PAID_AT + 600
        # Verifying with Stripe backfills the real payment date and uses it.
        assert _verify(client, "cs_old_open").status_code == 200
        assert _row(tmp, "cs_old_open")["paid_at"] == PAID_AT
        clock.now = PAID_AT + DAY + 1
        assert _expired(_verify(client, "cs_old_open"))
        # The old finalized payment is kept and stays spent.
        resp = _verify(client, "cs_old_done")
        assert resp.status_code == 409 and resp.headers["x-batch-error"] == "already_used"
        assert _row(tmp, "cs_old_done")["status"] == "finalized"
        # Re-opening the app runs the migration again harmlessly.
    finally:
        client.__exit__(None, None, None)
    client, _ = _start(tmp, gateway, now=PAID_AT + 2 * HOUR)
    try:
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM batch_payments").fetchone()[0] == 2
            assert len(conn.execute("PRAGMA table_info(batch_payments)").fetchall()) == 6
    finally:
        client.__exit__(None, None, None)


# --- texts: FR / EN ------------------------------------------------------------------------------


def _fr_dict() -> dict[str, str]:
    src = (STATIC / "i18n-fr.js").read_text(encoding="utf-8")
    block = src[src.index("var dict = {"): src.index("var reprocessProfilesFr")]
    return dict(re.findall(r'"([\w.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', block))


def test_window_texts_exist_in_french_and_english():
    html = (STATIC / "batch.html").read_text(encoding="utf-8")
    fr = _fr_dict()
    # After payment.
    assert f'data-i18n="batch.lot.window">{EN_WINDOW}</p>' in html
    assert fr["batch.lot.window"] == FR_WINDOW
    assert html.index('id="view-lot"') < html.index("batch.lot.window") < html.index('id="lot-dropzone"')
    # Expired (runtime, from the API error code).
    assert fr["batch.err.payment_expired"] == FR_EXPIRED  # the English detail is asserted by _expired()
    # Before payment: the window is announced on the offer itself.
    buy = html.split('id="view-buy"')[1].split("</section>")[0]
    assert "24</span> hours after payment" in buy and buy.count("offer-window") == 2
    assert "hours after payment to finish the lot" in buy  # terms line under the button
    assert "24</span> heures après le paiement" in fr["batch.buy.fact6"] and "offer-window" in fr["batch.buy.terms"]
    assert "ZIP" in fr["batch.buy.fact6"] and "offer-zip-hours" in fr["batch.buy.fact6"]


def test_window_texts_are_served_and_translated_end_to_end(tmp):
    client, _ = _start(tmp)
    try:
        page = client.get("/batch").text
        assert EN_WINDOW in page and FR_WINDOW not in page
        # The French comes from the shared dictionary, applied by i18n-apply.js.
        assert 'src="static/i18n-fr.js"' in page and 'data-i18n="batch.lot.window"' in page
        offer = client.get("/api/batch/offer").json()
        assert offer["window_hours"] == 24 and offer["zip_hours"] == 1
        assert offer["price_cents"] == 199 and offer["min_files"] == 2 and offer["max_files"] == 50
        assert offer["max_upload_mb"] == 10 and offer["max_total_mb"] == 64
    finally:
        client.__exit__(None, None, None)
    js = (STATIC / "batch.js").read_text(encoding="utf-8")
    assert 'set("offer-window", String(offer.window_hours))' in js
    assert "resp.status === 410" in js  # the page stops the lot and shows the expiry text


# --- the free tool -------------------------------------------------------------------------------


def test_free_single_file_flow_is_unchanged_by_the_window(tmp):
    client, clock = _start(tmp, now=PAID_AT + 30 * DAY)  # whatever the clock says
    try:
        resp = client.post("/api/inspect/file", files={"file": ("photo.png", _png(), "image/png")})
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        assert client.post(f"/api/clean/{sid}").status_code == 200
        assert client.post(f"/api/verify/{sid}").status_code == 200
        assert client.get(f"/api/download/{sid}").status_code == 200
        resp = client.post("/api/inspect/text", json={"text": "plain text"})
        assert resp.status_code == 200
        assert "window_hours" not in client.get("/api/config").text and "paid_at" not in client.get("/").text
        assert not (tmp / "commerce.db").exists() or _row(tmp) is None  # the free flow writes no payment
    finally:
        client.__exit__(None, None, None)


def test_batch_module_constants_unchanged():
    assert batch_module.BATCH_WINDOW_SECONDS == 24 * 3600
    assert batch_module.RESULT_TTL_SECONDS == 3600
    assert batch_module.BATCH_MIN_FILES == 2 and batch_module.BATCH_MAX_TOTAL_MB == 64
