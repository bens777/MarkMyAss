"""Paid batch processing: one Stripe payment = one lot of 2 to 50 files.

The free single-file tool is untouched by this module. What is sold here is
only time saved: instead of cleaning files one at a time for free, a
visitor pays once (Stripe Checkout, one-time payment) to clean a lot of
2 to 50 images/PDFs through the very same cleaners, verifiers, Deep
Reprocess and receipts, and downloads every result in one ZIP.

Deliberately minimal (this is an MVP to test whether visitors pay):

- No account, no credits, no validity period, no e-mail, no private link.
  The Stripe Checkout Session id (``cs_...``, returned to the browser by
  Stripe's own success redirect) is the temporary proof of payment.
- It is NEVER trusted on its own: before a lot is opened the server asks
  Stripe's API that the session exists, is ``paid``, and matches this offer
  (amount, currency and the metadata we stamped at creation). Only then is
  a row written to the single table ``batch_payments``.
- One payment = one finalized lot. Opening the lot is ``INSERT OR IGNORE``
  on the UNIQUE session id, so two simultaneous requests can never create
  two lots; finalizing is a guarded UPDATE, so only one ZIP can ever close
  the lot. Failed or incomplete files can be replaced or retried for free
  until the ZIP exists; afterwards the payment is spent.
- Nothing but the session id, a status and two timestamps is stored. File
  names, contents, hashes, e-mails, IPs or full Stripe objects never reach
  the database, and the session id never reaches the logs.

Per-file pipeline (every step is an existing free-tool function, driven by
the browser one request at a time so the UI can show real progress):

    upload  -> clean_file()                       "Cleaning..."
    verify  -> verify_file(original, output)      "Verifying..."
              if the verdict is FAILED/PARTIAL because of a removable,
              non-statistical signal and the file is an image:
    deep    -> reprocess_image_bytes() (Deep Reprocess, default profile)
                                                  "Deep cleaning..."
    verify  -> verify_file(original, deep output) "Verifying again..."
    done    -> build_receipt() from the FINAL verification

Final statuses: ``verified`` only when GhostMark's re-inspection passes AND
every independent verifier that actually ran agrees; otherwise
``incomplete`` (downloadable, but flagged everywhere -- including when the
automatic Deep Reprocess itself fails, in which case the standard clean
output is kept); ``failed`` only when no usable cleaned output exists. Deep cleaning is never triggered by a non-removable warning, a
known limitation (no verifier available) or a statistical watermark, which
the verifier reports as UNKNOWN, not FOUND.

Temporary results live under the OS temp dir (the /tmp tmpfs in
production), are deleted when zipped or after one hour by the app's
existing TTL sweeper, and their total size per lot is capped so a batch
can never exhaust the tmpfs the free tool depends on.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sqlite3
import tempfile
import threading
import time
import zipfile
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ghostmark.cleaner import clean_file
from ghostmark.models import Category, VerifyResult
from ghostmark.receipt import build_receipt
from ghostmark.reprocess import DEFAULT_PROFILE, reprocess_image_bytes
from ghostmark.security import sanitize_filename, sniff_mime_matches_extension, suffix_of
from ghostmark.verifier import verify_file
from ghostmark.web.concurrency import ProcessingTimeoutError, ServerBusyError
from ghostmark.web.config import WebConfig

log = logging.getLogger("ghostmark.web.batch")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
BATCH_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}  # images + PDF only; text/Word excluded
BATCH_MIN_FILES = 2
BATCH_CURRENCY = "eur"
# Total size of one lot's inputs. Outputs wait on the /tmp tmpfs (256 MB in
# production, shared with the free tool) until the ZIP is built, and the ZIP
# is roughly the same size again, so 64 MB keeps the worst case under 140 MB.
BATCH_MAX_TOTAL_MB = 64
RESULT_TTL_SECONDS = 60 * 60
WORKDIR_PREFIX = "ghostmark-batch-"
SESSION_HEADER = "x-batch-session"
DEEP_CLEAN_PROFILE = DEFAULT_PROFILE  # the same default the free Deep Reprocess UI pre-selects
DEEP_CLEAN_FAILED_WARNING = "Deep cleaning failed; the standard clean output was kept and is NOT independently verified"
_CHECKOUT_METADATA = {"markmyass": "batch"}
_UPLOAD_READ_CHUNK = 1024 * 1024

# Routes that carry the verified Stripe session (never a bare anonymous
# call) and legitimately burst above the anonymous per-IP budget while a lot
# is processed -- excluded from the IP rate limiter.
RATE_LIMIT_EXEMPT_PREFIXES = ("/api/batch/files", "/api/batch/finalize", "/api/batch/zip")


def _err(status: int, code: str, message: str) -> HTTPException:
    """An API error with an English `detail` (unchanged contract) plus a stable
    machine code in the X-Batch-Error header, so batch.js can show the French
    text from the shared i18n dictionary (batch.err.<code>)."""

    return HTTPException(status_code=status, detail=message, headers={"X-Batch-Error": code})


# --- storage ------------------------------------------------------------------------


class PaymentStore:
    """The single-table SQLite store. Every write is one transaction under a
    process lock (same pattern as ghostmark.web.stats)."""

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS batch_payments ("
                "  id INTEGER PRIMARY KEY,"
                "  stripe_session_id TEXT NOT NULL UNIQUE,"
                "  status TEXT NOT NULL CHECK (status IN ('paid', 'processing', 'finalized')),"
                "  created_at REAL NOT NULL,"
                "  finalized_at REAL)"
            )

    def open_lot(self, stripe_session_id: str, now: float | None = None) -> sqlite3.Row:
        """Register a Stripe-verified payment and return its row.

        INSERT OR IGNORE on the UNIQUE session id: concurrent calls for the
        same payment all land on the same single row (one payment, one lot).
        """

        now = time.time() if now is None else now
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT OR IGNORE INTO batch_payments (stripe_session_id, status, created_at) VALUES (?, 'paid', ?)",
                (stripe_session_id, now),
            )
            return conn.execute("SELECT * FROM batch_payments WHERE stripe_session_id = ?", (stripe_session_id,)).fetchone()

    def get(self, stripe_session_id: str) -> sqlite3.Row | None:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT * FROM batch_payments WHERE stripe_session_id = ?", (stripe_session_id,)).fetchone()

    def mark_processing(self, payment_id: int) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE batch_payments SET status = 'processing' WHERE id = ? AND status = 'paid'", (payment_id,))

    def finalize(self, payment_id: int, now: float | None = None) -> bool:
        """Spend the payment. Guarded so it can happen exactly once."""

        now = time.time() if now is None else now
        with self._lock, closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "UPDATE batch_payments SET status = 'finalized', finalized_at = ? WHERE id = ? AND status != 'finalized'",
                (now, payment_id),
            )
            return cur.rowcount == 1


# --- Stripe gateway (replaced by a fake in tests) --------------------------------------


class StripeGateway:
    """Thin wrapper over the official SDK: the two calls the MVP needs."""

    def __init__(self, *, secret_key: str, price_id: str) -> None:
        self._secret_key = secret_key
        self._price_id = price_id

    def _client(self):
        import stripe

        stripe.api_key = self._secret_key
        return stripe

    def create_checkout_session(self, *, success_url: str, cancel_url: str, locale: str) -> str:
        session = self._client().checkout.Session.create(
            mode="payment",
            line_items=[{"price": self._price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            # Stripe's hosted page follows the visitor's chosen UI language.
            locale="fr" if locale == "fr" else "en",
            metadata=_CHECKOUT_METADATA,
        )
        return session["url"]

    def retrieve_session(self, session_id: str) -> dict[str, Any] | None:
        """The handful of fields the server verifies, or None if Stripe has no such session."""

        stripe = self._client()
        try:
            s = stripe.checkout.Session.retrieve(session_id)
        except stripe.StripeError:
            return None
        return session_fields(s)


def session_fields(session: Any) -> dict[str, Any]:
    """Normalize what Stripe returns into a plain dict of the fields we verify.

    The SDK returns a ``StripeObject`` -- NOT a dict (since stripe-python 13
    it no longer subclasses dict, so ``.get()`` does not exist on it). It
    does expose ``to_dict()``, so convert first and only then read fields.
    """

    s = session.to_dict() if hasattr(session, "to_dict") else dict(session)
    return {
        "id": s["id"],
        "mode": s.get("mode"),
        "payment_status": s.get("payment_status"),
        "amount_total": s.get("amount_total"),
        "currency": s.get("currency"),
        "metadata": dict(s.get("metadata") or {}),
    }


# --- per-file state + verification assessment ---------------------------------------------


@dataclass
class FileState:
    """Sidecar JSON next to one file's temp outputs (never in the database)."""

    key: str
    name: str  # sanitized original file name
    ext: str  # original extension
    out_suffix: str  # extension of the current/final output (Deep Reprocess may change it)
    stage: str  # cleaned | needs_deep_clean | deep_cleaned | done
    status: str = ""  # verified | incomplete (set when stage == done)
    deep_used: bool = False
    deep_clean_failed: bool = False  # Deep Reprocess raised; the standard clean output was kept
    first_verdict: str = ""
    final_verdict: str = ""
    warnings: list[str] = field(default_factory=list)

    def dump(self, workdir: Path) -> None:
        (workdir / f"{self.key}.state.json").write_text(json.dumps(asdict(self)), encoding="utf-8")

    @classmethod
    def load(cls, workdir: Path, key: str) -> FileState | None:
        path = workdir / f"{key}.state.json"
        if not path.exists():
            return None
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def public(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "status": self.status,
            "deep_used": self.deep_used,
            "deep_clean_failed": self.deep_clean_failed,
            "first_verdict": self.first_verdict,
            "final_verdict": self.final_verdict,
            "warnings": list(self.warnings),
            "download_name": f"{Path(self.name).stem}.ghostmark{self.out_suffix}",
        }


def assess_verification(vr: VerifyResult) -> dict[str, Any]:
    """Turn the verifier's structured result into the batch decision.

    ``verified``: GhostMark's own re-inspection finds every supported signal
    gone AND at least one independent verifier actually ran and agreed.
    ``cleanable_remaining`` is what may justify Deep Reprocess: a removable,
    non-statistical detector still FOUND after cleaning, or an independent
    verifier that ran and still finds embedded data. Statistical watermarks
    are reported UNKNOWN (never in ``remaining``), a missing verifier is a
    known limitation, and non-removable findings cannot be helped -- none
    of those trigger a deep clean.
    """

    summary = vr.summary_v2
    verdict = summary.verdict.value if summary else "unverified"
    ran = [v for v in (summary.external_verifiers if summary else []) if v.passed is not None]
    verified = bool(summary and summary.ghostmark_pass and ran and all(v.passed for v in ran))

    warnings: list[str] = []
    cleanable = False
    for detector in vr.remaining:
        d = vr.after.get(detector)
        label = d.label if d else detector
        warnings.append(f"{label}: still detected after cleaning")
        if d is not None and d.removable and d.category is not Category.STATISTICAL:
            cleanable = True
    for v in ran:
        if v.passed is False:
            warnings.append(f"{v.label} still finds embedded data")
            cleanable = True
    if not ran:
        warnings.append("No independent verifier was available to confirm this result")

    return {
        "status": "verified" if verified else "incomplete",
        "verdict": verdict,
        "warnings": warnings,
        "cleanable_remaining": cleanable,
    }


# --- the feature --------------------------------------------------------------------


class CheckoutIn(BaseModel):
    # Files are selected only AFTER payment, so a checkout normally carries
    # just the locale. The optional counts are still validated when a client
    # sends them (the real limits are enforced at upload/finalize anyway).
    file_count: int | None = None
    total_bytes: int | None = None
    locale: str = "en"


class SessionIn(BaseModel):
    session_id: str


class BatchFeature:
    def __init__(self, *, config: WebConfig, store: PaymentStore, gateway: Any, run: Callable[..., Any],
                 record_public_clean: Callable[[], Any]) -> None:
        self.config = config
        self.store = store
        self.gateway = gateway
        self._run = run  # the app's BoundedRunner.run (timeout + concurrency cap)
        self._record_public_clean = record_public_clean
        self._tmp = Path(tempfile.gettempdir())
        self._locks: dict[int, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # -- helpers --------------------------------------------------------------------

    def _workdir(self, payment_id: int) -> Path:
        d = self._tmp / f"{WORKDIR_PREFIX}{payment_id}"
        d.mkdir(mode=0o700, exist_ok=True)
        return d

    def _lock(self, payment_id: int) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(payment_id, threading.Lock())

    def _states(self, workdir: Path) -> list[FileState]:
        states = []
        for p in workdir.glob("*.state.json"):
            st = FileState.load(workdir, p.name[: -len(".state.json")])
            if st:
                states.append((p.stat().st_mtime_ns, p.name, st))
        return [st for _, _, st in sorted(states, key=lambda x: (x[0], x[1]))]

    def _results(self, workdir: Path) -> list[FileState]:
        """Finished files (verified or incomplete) whose output is on disk, in upload order."""

        return [st for st in self._states(workdir) if st.stage == "done" and (workdir / f"{st.key}{st.out_suffix}").exists()]

    def _total_bytes(self, workdir: Path) -> int:
        return sum(
            p.stat().st_size
            for p in workdir.iterdir()
            if p.is_file() and not p.name.endswith((".state.json", ".name", ".receipt.json"))
        )

    def verify_payment(self, session_id: str) -> sqlite3.Row:
        """Ask Stripe, never the URL: exists, paid, and really this offer."""

        if not session_id.startswith("cs_") or len(session_id) > 128:
            raise _err(400, "invalid_session", "Invalid checkout session.")
        s = self.gateway.retrieve_session(session_id)
        if s is None or s.get("mode") != "payment" or s.get("payment_status") != "paid":
            raise _err(402, "not_paid", "Payment not confirmed by Stripe.")
        if (
            s.get("amount_total") != self.config.batch_price_cents
            or str(s.get("currency") or "").lower() != BATCH_CURRENCY
            or (s.get("metadata") or {}).get("markmyass") != _CHECKOUT_METADATA["markmyass"]
        ):
            raise _err(409, "offer_mismatch", "This payment does not match the batch offer.")
        return self.store.open_lot(session_id)

    def _authenticate(self, request: Request, *, allow_finalized: bool = False) -> sqlite3.Row:
        """Routes after verification: the lot must already be open in the DB,
        which only ever happens after a successful Stripe check."""

        session_id = request.headers.get(SESSION_HEADER, "").strip()
        row = self.store.get(session_id) if session_id.startswith("cs_") else None
        if row is None:
            raise _err(402, "not_verified", "Payment not verified. Reload the page from Stripe's confirmation.")
        if row["status"] == "finalized" and not allow_finalized:
            raise _err(409, "already_used", "This payment has already been used for a finalized lot.")
        return row

    def lot_payload(self, row: sqlite3.Row) -> dict[str, Any]:
        workdir = self._workdir(int(row["id"]))
        return {
            "status": row["status"],
            "min_files": BATCH_MIN_FILES,
            "max_files": self.config.batch_max_files,
            "max_upload_mb": self.config.max_upload_mb,
            "results": [st.public() for st in self._results(workdir)],
            "zip_available": any(p.suffix == ".zip" for p in workdir.iterdir()),
        }

    # -- temp-file lifecycle -------------------------------------------------------------

    def sweep(self, now: float | None = None) -> None:
        """Delete results/ZIPs older than one hour. Called by the app's
        existing 60-second TTL sweeper -- no new background machinery."""

        now = time.time() if now is None else now
        for d in self._tmp.glob(f"{WORKDIR_PREFIX}*"):
            if not d.is_dir():
                continue
            for p in d.iterdir():
                try:
                    if now - p.stat().st_mtime > RESULT_TTL_SECONDS:
                        p.unlink()
                except OSError:
                    pass
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    def _discard(self, workdir: Path, key: str) -> None:
        for p in workdir.glob(f"{key}*"):
            p.unlink(missing_ok=True)

    # -- step 1: upload + standard clean ------------------------------------------------------

    async def upload(self, request: Request, file: UploadFile) -> dict[str, Any]:
        row = self._authenticate(request)
        payment_id = int(row["id"])
        safe_name = sanitize_filename(file.filename or "upload")
        ext = suffix_of(safe_name)
        if ext not in BATCH_EXTENSIONS:
            raise _err(400, "unsupported_type", "Batch accepts images (PNG, JPEG, WebP) and PDF only.")

        workdir = self._workdir(payment_id)
        if len(self._states(workdir)) >= self.config.batch_max_files:
            raise _err(409, "lot_full", f"This lot already holds {self.config.batch_max_files} files.")

        max_bytes = self.config.max_upload_mb * 1024 * 1024
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > max_bytes + 64 * 1024:
            raise _err(413, "too_large", f"Upload exceeds the {self.config.max_upload_mb} MB limit.")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await file.read(_UPLOAD_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise _err(413, "too_large", f"Upload exceeds the {self.config.max_upload_mb} MB limit.")
            chunks.append(chunk)
        data = b"".join(chunks)
        if self._total_bytes(workdir) + len(data) > BATCH_MAX_TOTAL_MB * 1024 * 1024:
            raise _err(413, "lot_total_exceeded", f"A lot is limited to {BATCH_MAX_TOTAL_MB} MB in total.")
        if not sniff_mime_matches_extension(data, ext):
            raise _err(400, "mime_mismatch", "File content does not match its extension.")

        key = secrets.token_hex(8)
        original = workdir / f"{key}.orig{ext}"
        work = workdir / f"{key}.work{ext}"
        original.write_bytes(data)
        try:
            await run_in_threadpool(self._run, clean_file, original, output_path=work)
        except (ServerBusyError, ProcessingTimeoutError) as exc:
            self._discard(workdir, key)
            raise _err(503, "busy", str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - untrusted file content must never crash the server
            self._discard(workdir, key)
            log.warning("batch lot id=%s: a file failed to clean (%s)", payment_id, exc.__class__.__name__)
            raise _err(400, "failed", "Could not clean this file. You can retry or replace it.") from exc
        FileState(key=key, name=safe_name, ext=ext, out_suffix=ext, stage="cleaned").dump(workdir)
        self.store.mark_processing(payment_id)
        return {"key": key, "original_name": safe_name, "stage": "cleaned"}

    # -- step 2 (and 4): verification -----------------------------------------------------------

    def _load_state(self, workdir: Path, key: str, *stages: str) -> FileState:
        st = FileState.load(workdir, key) if key.isalnum() and len(key) <= 32 else None
        if st is None:
            raise _err(404, "unknown_file", "No such file in this lot.")
        if stages and st.stage not in stages:
            raise _err(409, "wrong_step", f"This file is at step '{st.stage}', not ready for this action.")
        return st

    def verify(self, request: Request, key: str) -> dict[str, Any]:
        row = self._authenticate(request)
        payment_id = int(row["id"])
        workdir = self._workdir(payment_id)
        with self._lock(payment_id):
            st = self._load_state(workdir, key, "cleaned", "deep_cleaned")
            original = workdir / f"{key}.orig{st.ext}"
            work = workdir / f"{key}.work{st.out_suffix}"
            try:
                vr: VerifyResult = self._run(verify_file, original, work)
            except (ServerBusyError, ProcessingTimeoutError) as exc:
                raise _err(503, "busy", str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                self._fail(workdir, st, exc)
                raise _err(400, "failed", "Could not verify this file. You can retry or replace it.") from exc
            # Same redaction as the single-file routes: never expose temp paths.
            vr.before.target = st.name
            vr.after.target = f"{Path(st.name).stem}.ghostmark{st.out_suffix}"
            verdict = assess_verification(vr)

            if st.stage == "cleaned":
                st.first_verdict = verdict["verdict"]
                if verdict["cleanable_remaining"] and st.ext in IMAGE_EXTENSIONS and not st.deep_used:
                    st.stage = "needs_deep_clean"
                    st.dump(workdir)
                    return {"key": key, "stage": "needs_deep_clean", "verdict": verdict["verdict"], "warnings": verdict["warnings"]}
            return self._finish_file(workdir, st, original, work, vr, verdict)

    def _finish_file(
        self, workdir: Path, st: FileState, original: Path, work: Path, vr: VerifyResult, verdict: dict[str, Any]
    ) -> dict[str, Any]:
        final = workdir / f"{st.key}{st.out_suffix}"
        work.rename(final)
        st.stage, st.status = "done", verdict["status"]
        st.final_verdict, st.warnings = verdict["verdict"], verdict["warnings"]
        receipt = build_receipt(
            file_name=f"{Path(st.name).stem}.ghostmark{st.out_suffix}",
            before_hash=hashlib.sha256(original.read_bytes()).hexdigest(),
            after_hash=hashlib.sha256(final.read_bytes()).hexdigest(),
            verify_result=vr,
        ).to_dict()
        receipt["batch"] = {
            "status": st.status,
            "deep_clean_used": st.deep_used,
            "deep_clean_failed": st.deep_clean_failed,
            "first_verification_verdict": st.first_verdict,
            "final_verification_verdict": st.final_verdict,
            "remaining_warnings": list(st.warnings),
        }
        (workdir / f"{st.key}.receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        (workdir / f"{st.key}.name").write_text(st.name, encoding="utf-8")
        original.unlink(missing_ok=True)
        st.dump(workdir)
        self._record_public_clean()  # same public "files cleaned" counter as the free tool
        return {"stage": "done", **st.public(), "results": len(self._results(workdir))}

    def _fail(self, workdir: Path, st: FileState, exc: Exception) -> None:
        log.warning("batch file failed at stage %s (%s)", st.stage, exc.__class__.__name__)
        self._discard(workdir, st.key)

    # -- step 3: Deep Reprocess, only when verification asked for it ------------------------------

    def deep_clean(self, request: Request, key: str) -> dict[str, Any]:
        row = self._authenticate(request)
        payment_id = int(row["id"])
        workdir = self._workdir(payment_id)
        with self._lock(payment_id):
            st = self._load_state(workdir, key, "needs_deep_clean")
            original = workdir / f"{key}.orig{st.ext}"
            try:
                result = self._run(reprocess_image_bytes, original.read_bytes(), st.ext, DEEP_CLEAN_PROFILE, None)
            except (ServerBusyError, ProcessingTimeoutError) as exc:
                raise _err(503, "busy", str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                # The standard clean already produced a usable output: keep it,
                # finish the file as INCOMPLETE (never verified) and say why.
                # `failed` is reserved for files with no usable cleaned output.
                log.warning("batch lot id=%s: deep clean failed (%s); standard output kept", payment_id, exc.__class__.__name__)
                return self._finish_after_deep_clean_failure(workdir, st, original)
            (workdir / f"{key}.work{st.out_suffix}").unlink(missing_ok=True)
            st.out_suffix = result.output_suffix
            (workdir / f"{key}.work{st.out_suffix}").write_bytes(result.output_bytes)
            st.deep_used, st.stage = True, "deep_cleaned"
            st.dump(workdir)
            return {"key": key, "stage": "deep_cleaned", "profile": result.profile}

    def _finish_after_deep_clean_failure(self, workdir: Path, st: FileState, original: Path) -> dict[str, Any]:
        work = workdir / f"{st.key}.work{st.out_suffix}"  # the standard clean output, untouched
        try:
            vr: VerifyResult = self._run(verify_file, original, work)
        except (ServerBusyError, ProcessingTimeoutError) as exc:
            raise _err(503, "busy", str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - no verification at all -> no receipt can be honest
            self._fail(workdir, st, exc)
            raise _err(400, "failed", "Could not verify this file. You can retry or replace it.") from exc
        vr.before.target = st.name
        vr.after.target = f"{Path(st.name).stem}.ghostmark{st.out_suffix}"
        verdict = assess_verification(vr)
        verdict["status"] = "incomplete"  # a deep clean was needed and could not run: never 'verified'
        verdict["warnings"] = [DEEP_CLEAN_FAILED_WARNING, *verdict["warnings"]]
        st.deep_clean_failed = True
        return self._finish_file(workdir, st, original, work, vr, verdict)

    def remove(self, request: Request, key: str) -> dict[str, Any]:
        """Drop one file (e.g. an incomplete one the customer wants to replace) before the ZIP exists."""

        row = self._authenticate(request)
        workdir = self._workdir(int(row["id"]))
        with self._lock(int(row["id"])):
            self._load_state(workdir, key)
            self._discard(workdir, key)
        return {"removed": key}

    # -- finalize + ZIP ----------------------------------------------------------------------

    def finalize(self, request: Request) -> dict[str, Any]:
        """Build the ZIP of every finished result (+ receipts), then spend the
        payment. If the ZIP cannot be built, nothing is spent and the lot can
        be retried; once spent, the ZIP stays downloadable for an hour."""

        row = self._authenticate(request, allow_finalized=True)
        payment_id = int(row["id"])
        workdir = self._workdir(payment_id)
        with self._lock(payment_id):
            existing = sorted(workdir.glob("*.zip"), key=lambda p: p.stat().st_mtime)
            if row["status"] == "finalized":
                if not existing:
                    raise _err(410, "zip_expired", "This payment was already used; its ZIP has expired.")
                return {"status": "finalized", "zip_name": existing[-1].name}
            results = self._results(workdir)
            if not results:
                raise _err(409, "no_results", "No successfully cleaned file yet.")
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            zip_path = workdir / f"markmyass-batch-{stamp}.zip"
            try:
                self._build_zip(workdir, results, zip_path)
            except Exception as exc:  # noqa: BLE001 - leave the lot retryable, spend nothing
                zip_path.unlink(missing_ok=True)
                log.warning("batch lot id=%s: ZIP build failed (%s)", payment_id, exc.__class__.__name__)
                raise _err(500, "zip_failed", "Could not build the ZIP. Please try again.") from exc
            if not self.store.finalize(payment_id):
                raise _err(409, "already_used", "This payment has already been used for a finalized lot.")
            for st in self._states(workdir):
                self._discard(workdir, st.key)
            log.info("batch lot id=%s finalized with %d file(s)", payment_id, len(results))
            return {
                "status": "finalized",
                "zip_name": zip_path.name,
                "results": len(results),
                "verified": sum(1 for st in results if st.status == "verified"),
                "incomplete": sum(1 for st in results if st.status == "incomplete"),
            }

    def _build_zip(self, workdir: Path, results: list[FileState], zip_path: Path) -> None:
        used: set[str] = set()
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"MarkMyAss batch results — {stamp}",
            "",
            "VERIFIED   = cleaned, and an independent verifier confirmed the supported signals are gone.",
            "INCOMPLETE = cleaned, but the final verification is not conclusive (see warnings). The file is",
            "             usable; it is NOT independently verified clean. Its name carries '-incomplete'.",
            "Each *-receipt.json holds the full verification receipt, including whether Deep Reprocess ran,",
            "the first and final verdicts and the remaining warnings.",
            "",
        ]
        with zipfile.ZipFile(zip_path, "w") as zf:
            for st in results:
                src = workdir / f"{st.key}{st.out_suffix}"
                stem = Path(st.name).stem
                tag = ".ghostmark" if st.status == "verified" else ".ghostmark-incomplete"
                arc = f"{stem}{tag}{st.out_suffix}"
                n = 2
                while arc.lower() in used:
                    arc = f"{stem} ({n}){tag}{st.out_suffix}"
                    n += 1
                used.add(arc.lower())
                # Images/PDF are already compressed: store, don't deflate.
                zf.write(src, arcname=arc, compress_type=zipfile.ZIP_STORED)
                receipt = workdir / f"{st.key}.receipt.json"
                if receipt.exists():
                    zf.write(receipt, arcname=f"{Path(arc).stem}-receipt.json", compress_type=zipfile.ZIP_DEFLATED)
                deep = "FAILED (standard clean kept)" if st.deep_clean_failed else ("yes" if st.deep_used else "no")
                lines.append(
                    f"{st.status.upper():<10} {arc}  |  deep clean: {deep}"
                    f"  |  first verdict: {st.first_verdict}  |  final verdict: {st.final_verdict}"
                )
                lines.extend(f"           warning: {w}" for w in st.warnings)
            zf.writestr("SUMMARY.txt", "\n".join(lines) + "\n", compress_type=zipfile.ZIP_DEFLATED)

    def download_zip(self, request: Request) -> FileResponse:
        row = self._authenticate(request, allow_finalized=True)
        workdir = self._workdir(int(row["id"]))
        zips = sorted(workdir.glob("*.zip"), key=lambda p: p.stat().st_mtime)
        if not zips:
            raise _err(404, "no_zip", "No ZIP for this lot (finalize it first, or it has expired).")
        return FileResponse(
            zips[-1],
            filename=zips[-1].name,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zips[-1].name}"'},
        )


# --- wiring ---------------------------------------------------------------------------


def install(
    app: FastAPI,
    *,
    config: WebConfig,
    run: Callable[..., Any],
    record_public_clean: Callable[[], Any],
    page_html: str,
    gateway: Any | None = None,
) -> BatchFeature | None:
    """Mount the paid batch feature on ``app``. Returns None (and mounts
    nothing) when the flag is off or the configuration is incomplete."""

    if not config.batch_enabled:
        return None
    if gateway is None:
        missing = [
            name
            for name, value in (
                ("GHOSTMARK_STRIPE_SECRET_KEY", config.stripe_secret_key),
                ("GHOSTMARK_STRIPE_PRICE_ID", config.stripe_price_id),
            )
            if not value
        ]
        if missing:
            log.warning("GHOSTMARK_BATCH_ENABLED is set but %s missing; batch feature stays off", ", ".join(missing))
            return None
        gateway = StripeGateway(secret_key=config.stripe_secret_key, price_id=config.stripe_price_id)

    db_path = config.commerce_db_path or str(Path(tempfile.gettempdir()) / "ghostmark-commerce.db")
    try:
        store = PaymentStore(db_path)
    except Exception as exc:  # noqa: BLE001 - a broken commerce DB must never take the free tool down
        log.warning("commerce DB unavailable (%s); batch feature stays off", exc.__class__.__name__)
        return None

    feature = BatchFeature(config=config, store=store, gateway=gateway, run=run, record_public_clean=record_public_clean)
    router = APIRouter()
    public_base = config.public_url.rstrip("/") + config.base_path.rstrip("/")

    @router.get("/batch", response_class=HTMLResponse)
    def batch_page() -> HTMLResponse:
        return HTMLResponse(page_html)

    @router.get("/api/batch/offer")
    def offer() -> dict[str, Any]:
        return {
            "price_cents": config.batch_price_cents,
            "currency": BATCH_CURRENCY,
            "min_files": BATCH_MIN_FILES,
            "max_files": config.batch_max_files,
            "max_upload_mb": config.max_upload_mb,
            "max_total_mb": BATCH_MAX_TOTAL_MB,
        }

    @router.post("/api/batch/checkout")
    def checkout(body: CheckoutIn) -> dict[str, str]:
        if body.file_count is not None and not BATCH_MIN_FILES <= body.file_count <= config.batch_max_files:
            raise _err(400, "bad_count", f"A lot holds between {BATCH_MIN_FILES} and {config.batch_max_files} files.")
        if body.total_bytes is not None and body.total_bytes > BATCH_MAX_TOTAL_MB * 1024 * 1024:
            raise _err(400, "bad_total", f"A lot is limited to {BATCH_MAX_TOTAL_MB} MB in total.")
        try:
            url = gateway.create_checkout_session(
                success_url=f"{public_base}/batch?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{public_base}/batch",
                locale=body.locale,
            )
        except Exception as exc:  # noqa: BLE001 - never leak Stripe internals
            log.warning("Stripe checkout creation failed: %s", exc.__class__.__name__)
            raise _err(502, "checkout_unavailable", "Payment service unavailable. Please try again.") from exc
        return {"url": url}

    @router.post("/api/batch/verify")
    def verify_session(body: SessionIn) -> dict[str, Any]:
        row = feature.verify_payment(body.session_id)
        if row["status"] == "finalized":
            raise _err(409, "already_used", "This payment has already been used for a finalized lot.")
        return feature.lot_payload(row)

    @router.post("/api/batch/files")
    async def upload(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
        return await feature.upload(request, file)

    @router.post("/api/batch/files/{key}/verify")
    def verify_file_step(request: Request, key: str) -> dict[str, Any]:
        return feature.verify(request, key)

    @router.post("/api/batch/files/{key}/deep-clean")
    def deep_clean_step(request: Request, key: str) -> dict[str, Any]:
        return feature.deep_clean(request, key)

    @router.delete("/api/batch/files/{key}")
    def remove_file(request: Request, key: str) -> dict[str, Any]:
        return feature.remove(request, key)

    @router.post("/api/batch/finalize")
    def finalize(request: Request) -> dict[str, Any]:
        return feature.finalize(request)

    @router.get("/api/batch/zip")
    def download_zip(request: Request) -> FileResponse:
        return feature.download_zip(request)

    app.include_router(router)
    return feature
