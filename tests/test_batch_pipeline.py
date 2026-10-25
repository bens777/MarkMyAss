"""Batch per-file pipeline decisions (clean -> verify -> conditional Deep
Reprocess -> verify again -> receipt) and the real Stripe SDK object shape.

The free tool's functions are replaced by fakes that return hand-built
VerifyResult objects, so every verifier outcome can be exercised without
ExifTool/c2patool installed. The decision logic under test is
ghostmark.web.batch.assess_verification + BatchFeature.verify/deep_clean."""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ghostmark.models import (
    Category,
    Confidence,
    DetectionResult,
    ExternalVerifierOutcome,
    InspectionReport,
    Status,
    VerificationSummary,
    VerifyResult,
)
from ghostmark.reprocess import ReprocessResult
from ghostmark.web import batch as batch_module
from ghostmark.web.app import create_app
from ghostmark.web.batch import StripeGateway, assess_verification, session_fields
from ghostmark.web.config import WebConfig

CS = "cs_test_pipeline"
STATIC = Path(__file__).resolve().parents[1] / "src" / "ghostmark" / "web" / "static"


# --- hand-built verifier results ----------------------------------------------------------


def _det(name, status, *, removable=True, category=Category.METADATA):
    return DetectionResult(detector=name, label=name.upper(), status=status, category=category, confidence=Confidence.HIGH, removable=removable)


def vr(*, found=("exif",), remaining=(), removable=True, externals=("pass",), statistical_unknown=False):
    """A VerifyResult as ghostmark.verifier would build it.

    externals: one entry per independent verifier -- "pass", "fail", or None
    (tool not available / not applicable, i.e. it did not run)."""

    before = [_det(n, Status.FOUND, removable=removable) for n in found]
    after = [_det(n, Status.FOUND if n in remaining else Status.NOT_FOUND, removable=removable) for n in found]
    unknown = []
    if statistical_unknown:
        before.append(_det("synthid", Status.UNKNOWN, removable=False, category=Category.STATISTICAL))
        after.append(_det("synthid", Status.UNKNOWN, removable=False, category=Category.STATISTICAL))
        unknown = ["synthid"]
    result = VerifyResult(
        before=InspectionReport(target="x", target_type="file", detections=before),
        after=InspectionReport(target="x", target_type="file", detections=after),
        resolved=[n for n in found if n not in remaining],
        remaining=list(remaining),
        unknown=unknown,
    )
    result.summary_v2 = VerificationSummary(
        ghostmark_pass=not remaining,
        supported_found_before=len(found),
        external_verifiers=[
            ExternalVerifierOutcome(
                name=f"tool{i}", label=f"Tool{i}", available=e is not None, applicable=e is not None,
                passed=None if e is None else e == "pass", version=None, note="",
            )
            for i, e in enumerate(externals)
        ],
        statistical_watermark_verified=False,
        c2pa_status="not_applicable",
        note="",
    )
    return result


# --- assess_verification: the exact deep-clean / verified rule --------------------------------


def test_conclusive_standard_clean_is_verified_and_needs_no_deep_clean():
    a = assess_verification(vr(externals=("pass", "pass")))
    assert a["status"] == "verified" and a["cleanable_remaining"] is False and a["warnings"] == []


def test_removable_signal_still_found_triggers_deep_clean():
    a = assess_verification(vr(remaining=("exif",), externals=("pass",)))
    assert a["status"] == "incomplete" and a["verdict"] == "failed" and a["cleanable_remaining"] is True
    assert a["warnings"] == ["EXIF: still detected after cleaning"]


def test_external_verifier_disagreement_triggers_deep_clean():
    a = assess_verification(vr(externals=("fail",)))
    assert a["status"] == "incomplete" and a["verdict"] == "partial" and a["cleanable_remaining"] is True
    assert a["warnings"] == ["Tool0 still finds embedded data"]


def test_non_removable_warning_known_limitation_or_statistical_never_trigger_deep_clean():
    # Non-removable leftover: cannot be helped by re-encoding.
    a = assess_verification(vr(remaining=("odd",), found=("odd",), removable=False, externals=("pass",)))
    assert a["status"] == "incomplete" and a["cleanable_remaining"] is False
    # No independent verifier available: a known limitation, not a cleaning problem.
    b = assess_verification(vr(externals=(None, None)))
    assert b["status"] == "incomplete" and b["verdict"] == "unverified" and b["cleanable_remaining"] is False
    assert b["warnings"] == ["No independent verifier was available to confirm this result"]
    # Statistical watermark reported UNKNOWN: never counts as remaining.
    c = assess_verification(vr(externals=("pass",), statistical_unknown=True))
    assert c["status"] == "verified" and c["cleanable_remaining"] is False


# --- the pipeline through the API, with the free tool's functions faked ----------------------


class FakeGateway:
    def create_checkout_session(self, **kwargs):
        return "https://checkout.stripe.test/session"

    def retrieve_session(self, session_id):
        return {"id": session_id, "mode": "payment", "payment_status": "paid", "amount_total": 199, "currency": "eur", "metadata": {"markmyass": "batch"}}


class Pipeline:
    """Records calls and serves scripted verification results."""

    def __init__(self) -> None:
        self.verifications: list = []
        self.calls = {"clean": 0, "verify": 0, "deep": 0}
        self.deep_raises = False

    def clean_file(self, path, *, output_path):
        self.calls["clean"] += 1
        output_path.write_bytes(path.read_bytes())

    def verify_file(self, original, cleaned):
        self.calls["verify"] += 1
        return self.verifications.pop(0)

    def reprocess_image_bytes(self, data, suffix, profile, out_format):
        self.calls["deep"] += 1
        if self.deep_raises:
            raise ValueError("cannot decode")
        return ReprocessResult(
            profile=profile, output_format="PNG", output_suffix=".png", output_bytes=b"\x89PNG\r\n\x1a\n" + b"deep",
            operations=["decode", "encode"], original_width=8, original_height=8, output_width=8, output_height=8,
            original_size_bytes=len(data), output_size_bytes=12, ssim=0.99, psnr=40.0, pixel_changed_pct=1.0,
            processing_time_ms=1.0, estimated_compute_cost=2.0,
        )


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    pipe = Pipeline()
    monkeypatch.setattr(batch_module, "clean_file", pipe.clean_file)
    monkeypatch.setattr(batch_module, "verify_file", pipe.verify_file)
    monkeypatch.setattr(batch_module, "reprocess_image_bytes", pipe.reprocess_image_bytes)
    cfg = WebConfig(
        mode="hosted", base_path="/", public_url="https://markmyass.test", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
        stats_db_path=str(tmp_path / "stats.db"), batch_enabled=True, commerce_db_path=str(tmp_path / "commerce.db"),
    )
    with TestClient(create_app(cfg, batch_gateway=FakeGateway())) as client:
        assert client.post("/api/batch/verify", json={"session_id": CS}).status_code == 200
        yield client, pipe


HDR = {"X-Batch-Session": CS}


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, name="a.png", data=None, mime="image/png"):
    resp = client.post("/api/batch/files", headers=HDR, files={"file": (name, data or _png(), mime)})
    assert resp.status_code == 200, resp.text
    assert resp.json()["stage"] == "cleaned"
    return resp.json()["key"]


def _verify(client, key):
    return client.post(f"/api/batch/files/{key}/verify", headers=HDR)


def _deep(client, key):
    return client.post(f"/api/batch/files/{key}/deep-clean", headers=HDR)


def test_conclusive_first_verification_finishes_without_deep_clean(env):
    client, pipe = env
    pipe.verifications = [vr(externals=("pass",))]
    key = _upload(client)
    body = _verify(client, key).json()
    assert body["stage"] == "done" and body["status"] == "verified" and body["deep_used"] is False
    assert body["first_verdict"] == "verified_clean" and body["final_verdict"] == "verified_clean" and body["warnings"] == []
    assert pipe.calls == {"clean": 1, "verify": 1, "deep": 0}
    # The deep-clean route refuses a file that does not need it.
    assert _deep(client, key).status_code == 409


def test_incomplete_and_cleanable_runs_deep_clean_exactly_once_then_verifies_again(env):
    client, pipe = env
    pipe.verifications = [vr(remaining=("exif",), externals=("pass",)), vr(externals=("pass",))]
    key = _upload(client)
    first = _verify(client, key).json()
    assert first["stage"] == "needs_deep_clean" and first["verdict"] == "failed"
    assert _verify(client, key).status_code == 409  # must deep-clean first; no silent second verification
    assert _deep(client, key).json()["stage"] == "deep_cleaned"
    assert _deep(client, key).status_code == 409  # exactly once
    final = _verify(client, key).json()
    assert final["stage"] == "done" and final["status"] == "verified" and final["deep_used"] is True
    assert final["first_verdict"] == "failed" and final["final_verdict"] == "verified_clean"
    assert pipe.calls == {"clean": 1, "verify": 2, "deep": 1}


def test_non_cleanable_warning_finishes_incomplete_without_deep_clean(env):
    client, pipe = env
    pipe.verifications = [vr(found=("odd",), remaining=("odd",), removable=False, externals=("pass",))]
    key = _upload(client)
    body = _verify(client, key).json()
    assert body["stage"] == "done" and body["status"] == "incomplete" and body["deep_used"] is False
    assert body["warnings"] == ["ODD: still detected after cleaning"]
    assert pipe.calls["deep"] == 0


def test_pdf_never_gets_deep_clean_even_when_cleanable(env):
    client, pipe = env
    pipe.verifications = [vr(externals=("fail",))]
    key = _upload(client, "doc.pdf", b"%PDF-1.4 fake", "application/pdf")
    body = _verify(client, key).json()
    assert body["stage"] == "done" and body["status"] == "incomplete" and body["deep_used"] is False
    assert pipe.calls["deep"] == 0


def test_second_verification_still_incomplete_keeps_warnings_and_never_says_verified(env):
    client, pipe = env
    pipe.verifications = [vr(externals=("fail",)), vr(externals=("fail",))]
    key = _upload(client)
    assert _verify(client, key).json()["stage"] == "needs_deep_clean"
    assert _deep(client, key).status_code == 200
    final = _verify(client, key).json()
    assert final["status"] == "incomplete" and final["deep_used"] is True
    assert final["first_verdict"] == "partial" and final["final_verdict"] == "partial"
    assert final["warnings"] == ["Tool0 still finds embedded data"]
    assert pipe.calls == {"clean": 1, "verify": 2, "deep": 1}


def test_deep_clean_failure_keeps_the_standard_output_as_incomplete(env):
    """Standard clean OK, automatic deep clean raises: the file is NOT failed --
    the standard output is kept, flagged incomplete with a deep_clean_failed
    warning, downloadable, removable, and never presented as verified."""

    client, pipe = env
    # First verification asks for a deep clean; the re-verification of the
    # kept standard output would, on its own, look conclusive -- it must
    # still be reported incomplete because the needed deep clean never ran.
    pipe.verifications = [vr(remaining=("exif",), externals=("pass",)), vr(externals=("pass",))]
    pipe.deep_raises = True
    key = _upload(client)
    assert _verify(client, key).json()["stage"] == "needs_deep_clean"

    resp = _deep(client, key)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stage"] == "done" and body["status"] == "incomplete"
    assert body["deep_used"] is False and body["deep_clean_failed"] is True
    assert body["warnings"][0].startswith("Deep cleaning failed; the standard clean output was kept")
    assert body["first_verdict"] == "failed"
    assert pipe.calls == {"clean": 1, "verify": 2, "deep": 1}

    lot = client.post("/api/batch/verify", json={"session_id": CS}).json()
    assert [(r["status"], r["deep_clean_failed"]) for r in lot["results"]] == [("incomplete", True)]
    # Removable (to replace or retry) before the ZIP exists...
    key2 = _upload(client, "b.png")
    pipe.verifications = [vr(externals=("pass",))]
    assert _verify(client, key2).json()["status"] == "verified"
    assert client.delete(f"/api/batch/files/{key2}", headers=HDR).status_code == 200
    # ...and downloadable, clearly flagged, in the ZIP.
    fin = client.post("/api/batch/finalize", headers=HDR).json()
    assert (fin["results"], fin["verified"], fin["incomplete"]) == (1, 0, 1)
    with zipfile.ZipFile(io.BytesIO(client.get("/api/batch/zip", headers=HDR).content)) as zf:
        names = set(zf.namelist())
        assert "a.ghostmark-incomplete.png" in names and "a.ghostmark.png" not in names
        receipt = json.loads(zf.read("a.ghostmark-incomplete-receipt.json"))
        assert receipt["batch"]["status"] == "incomplete"
        assert receipt["batch"]["deep_clean_used"] is False and receipt["batch"]["deep_clean_failed"] is True
        assert receipt["batch"]["remaining_warnings"][0].startswith("Deep cleaning failed")
        summary = zf.read("SUMMARY.txt").decode()
        assert "INCOMPLETE a.ghostmark-incomplete.png  |  deep clean: FAILED (standard clean kept)" in summary
        assert "warning: Deep cleaning failed; the standard clean output was kept" in summary
        assert "VERIFIED   a." not in summary


def test_failed_is_reserved_for_files_without_any_usable_output(env):
    client, pipe = env
    pipe.clean_file = lambda path, *, output_path: (_ for _ in ()).throw(ValueError("corrupt"))
    import ghostmark.web.batch as m
    m.clean_file = pipe.clean_file  # the fixture's monkeypatch restores the module attribute afterwards
    resp = client.post("/api/batch/files", headers=HDR, files={"file": ("bad.png", _png(), "image/png")})
    assert resp.status_code == 400 and resp.headers["x-batch-error"] == "failed"
    assert client.post("/api/batch/verify", json={"session_id": CS}).json()["results"] == []
    assert client.post("/api/batch/finalize", headers=HDR).status_code == 409


def test_receipts_and_summary_match_the_final_result(env):
    client, pipe = env
    pipe.verifications = [
        vr(externals=("pass",)),  # clean.png: verified, no deep clean
        vr(remaining=("exif",), externals=("pass",)), vr(externals=("pass",)),  # deep.png: deep clean then verified
        vr(externals=("fail",)), vr(externals=("fail",)),  # stubborn.png: deep clean, still incomplete
    ]
    for name in ("clean.png", "deep.png", "stubborn.png"):
        key = _upload(client, name)
        body = _verify(client, key).json()
        if body["stage"] == "needs_deep_clean":
            assert _deep(client, key).status_code == 200
            body = _verify(client, key).json()
        assert body["stage"] == "done"
    lot = client.post("/api/batch/verify", json={"session_id": CS}).json()
    assert [(r["name"], r["status"], r["deep_used"]) for r in lot["results"]] == [
        ("clean.png", "verified", False), ("deep.png", "verified", True), ("stubborn.png", "incomplete", True),
    ]
    fin = client.post("/api/batch/finalize", headers=HDR).json()
    assert (fin["results"], fin["verified"], fin["incomplete"]) == (3, 2, 1)

    with zipfile.ZipFile(io.BytesIO(client.get("/api/batch/zip", headers=HDR).content)) as zf:
        names = set(zf.namelist())
        assert {"clean.ghostmark.png", "deep.ghostmark.png", "stubborn.ghostmark-incomplete.png", "SUMMARY.txt"} <= names
        receipts = {n: json.loads(zf.read(n)) for n in names if n.endswith("-receipt.json")}
        assert receipts["clean.ghostmark-receipt.json"]["batch"] == {
            "status": "verified", "deep_clean_used": False, "deep_clean_failed": False,
            "first_verification_verdict": "verified_clean", "final_verification_verdict": "verified_clean",
            "remaining_warnings": [],
        }
        assert receipts["deep.ghostmark-receipt.json"]["batch"]["deep_clean_used"] is True
        assert receipts["deep.ghostmark-receipt.json"]["batch"]["first_verification_verdict"] == "failed"
        assert receipts["deep.ghostmark-receipt.json"]["verdict"] == "verified_clean"  # receipt built from the FINAL verification
        stubborn = receipts["stubborn.ghostmark-incomplete-receipt.json"]["batch"]
        assert stubborn["status"] == "incomplete" and stubborn["remaining_warnings"] == ["Tool0 still finds embedded data"]
        summary = zf.read("SUMMARY.txt").decode()
        assert "VERIFIED   clean.ghostmark.png  |  deep clean: no  |  first verdict: verified_clean  |  final verdict: verified_clean" in summary
        assert "VERIFIED   deep.ghostmark.png  |  deep clean: yes  |  first verdict: failed  |  final verdict: verified_clean" in summary
        assert "INCOMPLETE stubborn.ghostmark-incomplete.png  |  deep clean: yes  |  first verdict: partial  |  final verdict: partial" in summary
        assert "warning: Tool0 still finds embedded data" in summary


# --- UI statuses exist in both languages -----------------------------------------------------


def test_file_statuses_are_defined_in_french_and_english():
    js = (STATIC / "batch.js").read_text(encoding="utf-8")
    expected = {
        "cleaning": ("Cleaning…", "Nettoyage…"),
        "verifying": ("Verifying…", "Vérification…"),
        "deep": ("Deep cleaning…", "Nettoyage profond…"),
        "reverifying": ("Verifying again…", "Nouvelle vérification…"),
        "verified": ("Cleaned and verified", "Nettoyé et vérifié"),
        "incomplete": ("Cleaned — verification incomplete", "Nettoyé — vérification incomplète"),
        "failed": ("Processing failed", "Échec du traitement"),
    }
    for key, (en, fr) in expected.items():
        assert re.search(rf'{key}: \(\) => t\("{re.escape(en)}", "{re.escape(fr)}"\)', js), key
    assert 't(" · deep clean failed, standard clean kept", " · nettoyage profond échoué, nettoyage standard conservé")' in js
    assert 'if (data.stage !== "done")' in js  # a failed deep clean comes back already finished (incomplete)
    # "verified" is only ever shown for the server's final status, never assumed client-side.
    assert 'setRow(row, data.status, data)' in js and 'setRow(row, "verified"' not in js


# --- the real Stripe SDK object shape -------------------------------------------------------


class FakeStripeObject:
    """Reproduces stripe.StripeObject (>= v13): no dict inheritance, no .get(),
    item access and to_dict() only."""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def to_dict(self):
        return dict(self._data)


_RAW = {"id": CS, "object": "checkout.session", "mode": "payment", "payment_status": "paid",
        "amount_total": 199, "currency": "eur", "metadata": {"markmyass": "batch"}, "created": 1_800_000_000}


def test_session_fields_converts_a_stripe_object_with_to_dict_and_no_get():
    obj = FakeStripeObject(_RAW)
    assert not hasattr(obj, "get")  # the previous implementation called s.get(...) -> AttributeError
    with pytest.raises(AttributeError):
        obj.get("mode")  # type: ignore[attr-defined]
    assert session_fields(obj) == {
        "id": CS, "mode": "payment", "payment_status": "paid", "amount_total": 199, "currency": "eur",
        "metadata": {"markmyass": "batch"}, "created": 1_800_000_000,  # Stripe's own time: origin of the 24-hour window
    }
    assert session_fields(dict(_RAW)) == session_fields(obj)  # plain dicts (tests, fakes) still work


def test_retrieve_session_works_with_the_sdk_object_shape(monkeypatch):
    stripe = pytest.importorskip("stripe")
    assert not issubclass(stripe.StripeObject, dict), "if this flips, the to_dict() conversion is merely redundant"
    real = stripe.checkout.Session.construct_from(dict(_RAW), "sk_test_dummy")  # a genuine StripeObject
    assert isinstance(real, stripe.StripeObject) and not isinstance(real, dict) and not hasattr(real, "get")
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", classmethod(lambda cls, sid, **kw: real))
    gw = StripeGateway(secret_key="sk_test_dummy", price_id="price_x")
    assert gw.retrieve_session(CS) == session_fields(dict(_RAW))
