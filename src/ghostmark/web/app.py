"""FastAPI application for GhostMark's web UI -- local desktop mode and the
public moseisley.sh/ghostmark hosted deployment share this same app.

Design constraints enforced here:
  - No route ever proxies or fetches anything over the network.
  - Uploaded files are stored only in a per-session temp directory under the
    OS temp dir, with a randomized session id and a sanitized filename.
  - Sessions (and their temp files) are cleaned up after a TTL (10-15
    minutes, see WebConfig), on explicit delete, and on process exit --
    nothing lingers on disk. A session is intentionally NOT deleted the
    instant the cleaned file is downloaded, because the verification
    receipt is a separate, later download of the same session.
  - No CORS headers are ever added -- the frontend is same-origin only.
  - The caller (ghostmark.cli.ui, or the production Docker CMD) is
    responsible for choosing the bind address; this module never binds a
    socket itself. Local mode binds 127.0.0.1 only; the hosted deployment
    is only reachable through its reverse proxy (see DEPLOY_MOSEISLEY.md).
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import secrets
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ghostmark import __version__
from ghostmark.cleaner import clean_file, clean_text_content
from ghostmark.independent_verify import C2paToolVerifier, ExifToolVerifier
from ghostmark.inspector import inspect_file, inspect_text
from ghostmark.models import CleanResult, VerifyResult
from ghostmark.receipt import VerificationReceipt, build_receipt
from ghostmark.security import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    check_supported,
    sanitize_filename,
    sniff_mime_matches_extension,
    suffix_of,
)
from ghostmark.verifier import verify_file, verify_text
from ghostmark.web import lab_data
from ghostmark.web.benchmarks import run_benchmarks, to_markdown_table, to_summary_markdown
from ghostmark.web.concurrency import BoundedRunner, ProcessingTimeoutError, ServerBusyError
from ghostmark.web.config import WebConfig, load_config
from ghostmark.web.content_render import (
    CONTENT_DIR,
    PageMeta,
    inject_context,
    render_article_page,
    render_markdown_to_html,
)
from ghostmark.web.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware

STATIC_DIR = Path(__file__).parent / "static"
TTL_SWEEP_INTERVAL_SECONDS = 60

RUN_LOCAL_PAGE_META = PageMeta(
    title="Run AI Models Locally — Avoid Provider-Side Provenance at the Source | GhostMark",
    description=(
        "A practical developer guide to running open-weight AI models locally or on rented "
        "GPUs. Compare models, hardware, budgets, and installation paths."
    ),
    path="/run-local",
)
_ARTICLE_NAV_HTML = '<header class="article-header"><a href="." class="brand-link">👻 GhostMark</a></header>'

# AI Watermark Lab pages: "" is /lab itself, everything else is /lab/<slug>.
LAB_PAGE_META: dict[str, PageMeta] = {
    "": PageMeta(
        title="GhostMark AI Watermark Lab — Proof, Not Promises",
        description=(
            "A living, honest technical reference for AI watermark and provenance signals: "
            "what GhostMark can detect, remove, and independently verify -- and what it can't."
        ),
        path="/lab",
    ),
    "claude-watermark": PageMeta(
        title='Lab: "Claude Watermark" — Metadata vs. Hidden Unicode vs. Statistical Watermarking | GhostMark',
        description=(
            "Three different things get called the 'Claude watermark.' This page separates "
            "file metadata, hidden Unicode, and statistical text watermarking -- and is honest "
            "about which of them can actually be tested today."
        ),
        path="/lab/claude-watermark",
    ),
    "c2pa": PageMeta(
        title="Lab: C2PA / Content Credentials — Detection, Removal, Limits | GhostMark",
        description="What GhostMark's C2PA support actually does: JUMBF container detection, "
        "not cryptographic manifest validation. Methodology, commands, and sources.",
        path="/lab/c2pa",
    ),
    "hidden-unicode": PageMeta(
        title="Lab: Hidden Unicode — Detection & Removal Methodology | GhostMark",
        description="How GhostMark detects and safely removes hidden/invisible Unicode "
        "characters from text, and why load-bearing characters are preserved by default.",
        path="/lab/hidden-unicode",
    ),
    "pdf-metadata": PageMeta(
        title="Lab: PDF Metadata — DocInfo & XMP Detection and Removal | GhostMark",
        description="How GhostMark detects and removes PDF DocInfo and XMP metadata, "
        "independently verified with ExifTool, without altering page content.",
        path="/lab/pdf-metadata",
    ),
}
_slug_to_key = {
    "claude-watermark": "claude_statistical_watermark",
    "c2pa": "c2pa",
    "hidden-unicode": "hidden_unicode",
    "pdf-metadata": "pdf_metadata",
}

BENCHMARKS_PAGE_META = PageMeta(
    title="GhostMark Benchmarks — Real Results From the Public Test Corpus",
    description="Detection, cleaning, and independent-verification pass rates generated by "
    "actually running GhostMark's reproducible test corpus -- not hand-typed numbers.",
    path="/benchmarks",
)

log = logging.getLogger("ghostmark.web")


class _Session:
    def __init__(self, kind: str) -> None:
        self.kind = kind  # "text" | "file"
        self.workdir = Path(tempfile.mkdtemp(prefix="ghostmark-session-"))
        self.text: str | None = None
        self.cleaned_text: str | None = None
        self.original_path: Path | None = None
        self.cleaned_path: Path | None = None
        self.original_name: str = ""
        self.created_at = time.time()
        self.clean_result: CleanResult | None = None
        self.verify_result: VerifyResult | None = None

    def is_expired(self, ttl_seconds: float) -> bool:
        return (time.time() - self.created_at) > ttl_seconds

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


class _SessionStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()
        self.ttl_seconds = ttl_seconds

    def create(self, kind: str) -> tuple[str, _Session]:
        session_id = secrets.token_urlsafe(24)
        session = _Session(kind)
        with self._lock:
            self._sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str) -> _Session:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown or expired session.")
        return session

    def drop(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            session.cleanup()

    def sweep_expired(self) -> None:
        with self._lock:
            expired_ids = [sid for sid, s in self._sessions.items() if s.is_expired(self.ttl_seconds)]
            expired = [self._sessions.pop(sid) for sid in expired_ids]
        for session in expired:
            session.cleanup()

    def cleanup_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.cleanup()


class TextIn(BaseModel):
    text: str


def _inject_base_href(html: str, base_path: str) -> str:
    """Rewrite the page so every relative link resolves correctly when served
    under a reverse-proxy subpath (see /ghostmark deployment)."""

    return html.replace("<head>", f'<head>\n  <base href="{base_path}">', 1)


_UPLOAD_READ_CHUNK = 1024 * 1024  # 1 MB


async def _read_upload_bounded(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload in chunks, aborting as soon as it exceeds ``max_bytes``.

    Avoids buffering an arbitrarily large body into memory before the size
    check runs (a client can lie about or omit Content-Length).
    """

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"Upload exceeds the {max_bytes / (1024 * 1024):.0f} MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(config: WebConfig | None = None) -> FastAPI:
    config = config or load_config()

    app = FastAPI(title="GhostMark", version=__version__, docs_url=None, redoc_url=None)
    app.state.config = config

    store = _SessionStore(ttl_seconds=config.session_ttl_seconds)
    app.state.store = store  # exposed for tests/introspection, not used by any route
    atexit.register(store.cleanup_all)

    runner = BoundedRunner(max_concurrent=config.max_concurrent_jobs, timeout_seconds=config.processing_timeout_seconds)
    app.state.runner = runner
    atexit.register(runner.shutdown)

    exif_verifier = ExifToolVerifier()
    c2patool_verifier = C2paToolVerifier()

    stop_sweeper = threading.Event()

    def _sweep_loop() -> None:
        while not stop_sweeper.wait(TTL_SWEEP_INTERVAL_SECONDS):
            store.sweep_expired()

    sweeper_thread = threading.Thread(target=_sweep_loop, daemon=True, name="ghostmark-session-ttl-sweeper")
    sweeper_thread.start()
    atexit.register(stop_sweeper.set)

    # No CORS middleware is added intentionally: the frontend is served
    # same-origin by this app, so there is no legitimate cross-origin
    # caller and no Access-Control-Allow-Origin should ever be sent.
    app.add_middleware(RateLimitMiddleware, requests_per_minute=config.rate_limit_per_minute)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internals (paths, tracebacks) to the client.
        log.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc.__class__.__name__)
        return JSONResponse({"detail": "An unexpected error occurred."}, status_code=500)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        index_path = STATIC_DIR / "index.html"
        html = index_path.read_text(encoding="utf-8")
        return HTMLResponse(_inject_base_href(html, config.base_path))

    # Rendered once per process -- the content is a static file, not
    # per-request state, so there's no reason to re-run the Markdown
    # parser on every hit.
    _run_local_html = render_article_page(
        meta=RUN_LOCAL_PAGE_META,
        body_html=render_markdown_to_html((CONTENT_DIR / "run_local.md").read_text(encoding="utf-8")),
        base_path=config.base_path,
        public_url=config.public_url,
        nav_html=_ARTICLE_NAV_HTML,
    )

    @app.get("/run-local", response_class=HTMLResponse)
    def run_local() -> HTMLResponse:
        return HTMLResponse(_run_local_html)

    # --- AI Watermark Lab -------------------------------------------------------------
    # Every page's HTML is rendered once at startup from Markdown + the
    # capability data in ghostmark.web.lab_data -- the single source of
    # truth every surface (matrix table, per-signal status lines, and the
    # /api/lab/status JSON) reads from, so they can't drift apart.

    _lab_pages: dict[str, str] = {}
    for _slug, _meta in LAB_PAGE_META.items():
        _md_path = CONTENT_DIR / "lab" / ("index.md" if _slug == "" else f"{_slug}.md")
        _context = {"MATRIX_TABLE": lab_data.to_markdown_table()}
        if _slug:
            _context["STATUS_LINE"] = lab_data.to_status_line(_slug_to_key.get(_slug, ""))
        _md_text = inject_context(_md_path.read_text(encoding="utf-8"), _context)
        _lab_pages[_slug] = render_article_page(
            meta=_meta,
            body_html=render_markdown_to_html(_md_text),
            base_path=config.base_path,
            public_url=config.public_url,
            nav_html=_ARTICLE_NAV_HTML,
        )

    @app.get("/lab", response_class=HTMLResponse)
    def lab_index() -> HTMLResponse:
        return HTMLResponse(_lab_pages[""])

    @app.get("/lab/{slug}", response_class=HTMLResponse)
    def lab_page(slug: str) -> HTMLResponse:
        html = _lab_pages.get(slug)
        if html is None:
            raise HTTPException(status_code=404, detail="No such Lab page.")
        return HTMLResponse(html)

    @app.get("/api/lab/status")
    def lab_status() -> dict[str, Any]:
        return {
            "ghostmark_version": __version__,
            "tested_at": lab_data.LAST_REVIEWED,
            "signals": [s.to_dict() for s in lab_data.LAB_SIGNALS],
        }

    # --- Benchmarks ---------------------------------------------------------------------
    # Run once at startup against the real corpus -- not hand-typed numbers.
    # If the corpus or pipeline ever regresses, this page shows it, and so
    # does tests/test_corpus.py (same corpus, same expectations).

    _benchmark_report = run_benchmarks()
    _benchmarks_html = render_article_page(
        meta=BENCHMARKS_PAGE_META,
        body_html=render_markdown_to_html(
            inject_context(
                (CONTENT_DIR / "benchmarks.md").read_text(encoding="utf-8"),
                {
                    "SUMMARY": to_summary_markdown(_benchmark_report),
                    "TABLE": to_markdown_table(_benchmark_report),
                },
            )
        ),
        base_path=config.base_path,
        public_url=config.public_url,
        nav_html=_ARTICLE_NAV_HTML,
    )

    @app.get("/benchmarks", response_class=HTMLResponse)
    def benchmarks_page() -> HTMLResponse:
        return HTMLResponse(_benchmarks_html)

    @app.get("/api/benchmarks")
    def benchmarks_api() -> dict[str, Any]:
        return _benchmark_report.to_dict()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "ghostmark": __version__,
            "exiftool_available": exif_verifier.available(),
            "c2patool_available": c2patool_verifier.available(),
        }

    @app.get("/api/config")
    def api_config() -> dict[str, Any]:
        return {
            "mode": config.mode,
            "base_path": config.base_path,
            "public_url": config.public_url,
            "max_upload_mb": config.max_upload_mb,
            "session_ttl_minutes": config.session_ttl_seconds // 60,
            "exiftool_available": exif_verifier.available(),
            "exiftool_version": exif_verifier.version(),
            "c2patool_available": c2patool_verifier.available(),
            "c2patool_version": c2patool_verifier.version(),
            "ghostmark_version": __version__,
        }

    @app.post("/api/inspect/text")
    def inspect_text_route(body: TextIn) -> dict[str, Any]:
        session_id, session = store.create("text")
        session.text = body.text
        try:
            report = runner.run(inspect_text, body.text)
        except (ServerBusyError, ProcessingTimeoutError) as exc:
            store.drop(session_id)
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"session_id": session_id, "report": report.to_dict()}

    @app.post("/api/inspect/file")
    async def inspect_file_route(request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
        max_bytes = config.max_upload_mb * 1024 * 1024

        safe_name = sanitize_filename(file.filename or "upload")
        try:
            check_supported(safe_name)
        except UnsupportedFileTypeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Reject early from the declared Content-Length when present, before
        # reading any body at all.
        declared_length = request.headers.get("content-length")
        if declared_length and declared_length.isdigit() and int(declared_length) > max_bytes:
            raise HTTPException(status_code=413, detail=f"Upload exceeds the {config.max_upload_mb} MB limit.")

        try:
            data = await _read_upload_bounded(file, max_bytes)
        except FileTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc

        if not sniff_mime_matches_extension(data, suffix_of(safe_name)):
            raise HTTPException(status_code=400, detail="File content does not match its extension.")

        session_id, session = store.create("file")
        session.original_name = safe_name
        session.original_path = session.workdir / f"original{Path(safe_name).suffix.lower()}"
        session.original_path.write_bytes(data)

        try:
            # This route is async (it awaits the upload body), so the
            # blocking runner call must go through the threadpool -- calling
            # it directly here would stall the event loop for every other
            # concurrent request.
            report = await run_in_threadpool(runner.run, inspect_file, session.original_path)
        except (ServerBusyError, ProcessingTimeoutError) as exc:
            store.drop(session_id)
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - untrusted file content must never crash the server
            store.drop(session_id)
            log.warning("inspect failed for an uploaded file: %s", exc.__class__.__name__)
            raise HTTPException(status_code=400, detail="Could not inspect this file.") from exc

        return {"session_id": session_id, "report": report.to_dict()}

    @app.post("/api/clean/{session_id}")
    def clean_route(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        try:
            if session.kind == "text":
                if session.text is None:
                    raise HTTPException(status_code=400, detail="No text in this session.")
                cleaned, result = runner.run(clean_text_content, session.text)
                session.cleaned_text = cleaned
                session.clean_result = result
                payload = result.to_dict()
                payload["cleaned_text"] = cleaned
                return payload

            if session.original_path is None:
                raise HTTPException(status_code=400, detail="No file in this session.")
            result = runner.run(clean_file, session.original_path)
        except (ServerBusyError, ProcessingTimeoutError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("clean failed for session: %s", exc.__class__.__name__)
            raise HTTPException(status_code=400, detail="Could not clean this file.") from exc

        session.cleaned_path = Path(result.output)
        session.clean_result = result
        return result.to_dict()

    @app.post("/api/verify/{session_id}")
    def verify_route(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        try:
            if session.kind == "text":
                if session.text is None or session.cleaned_text is None:
                    raise HTTPException(status_code=400, detail="Run clean before verify.")
                result = runner.run(verify_text, session.text, session.cleaned_text)
                session.verify_result = result
                return result.to_dict()

            if session.original_path is None or session.cleaned_path is None:
                raise HTTPException(status_code=400, detail="Run clean before verify.")
            result = runner.run(verify_file, session.original_path, session.cleaned_path)
            session.verify_result = result
            return result.to_dict()
        except (ServerBusyError, ProcessingTimeoutError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/download/{session_id}")
    def download_route(session_id: str) -> FileResponse:
        session = store.get(session_id)
        if session.kind != "file" or session.cleaned_path is None or not session.cleaned_path.exists():
            raise HTTPException(status_code=400, detail="No cleaned file available for this session.")
        stem = Path(session.original_name).stem
        suffix = Path(session.original_name).suffix
        download_name = f"{stem}.ghostmark{suffix}"

        # Deliberately NOT single-use: a Verification Receipt for this same
        # session is typically downloaded right after the cleaned file, so
        # deleting on first download would break that. The TTL sweep (see
        # WebConfig.session_ttl_seconds, 10-15 minutes) is what guarantees
        # cleanup instead.
        return FileResponse(
            session.cleaned_path,
            filename=download_name,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    def _build_session_receipt(session: _Session) -> VerificationReceipt:
        if session.verify_result is None:
            raise HTTPException(status_code=400, detail="Run verify before requesting a receipt.")
        if session.kind == "text":
            file_name = "pasted-text"
            before_hash = hashlib.sha256((session.text or "").encode("utf-8")).hexdigest()
            after_hash = hashlib.sha256((session.cleaned_text or "").encode("utf-8")).hexdigest()
        else:
            file_name = Path(session.original_name).stem + ".ghostmark" + Path(session.original_name).suffix
            before_hash = session.clean_result.before_hash if session.clean_result else ""
            after_hash = session.clean_result.after_hash if session.clean_result else ""
        return build_receipt(
            file_name=file_name, before_hash=before_hash, after_hash=after_hash, verify_result=session.verify_result
        )

    @app.get("/api/receipt/{session_id}")
    def receipt_route(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        return _build_session_receipt(session).to_dict()

    @app.get("/api/receipt/{session_id}/download")
    def receipt_download_route(session_id: str, format: str = Query("json", pattern="^(json|html|txt)$")):
        session = store.get(session_id)
        receipt = _build_session_receipt(session)
        base_name = Path(receipt.file_name).stem or "ghostmark"

        renderers = {
            "html": (receipt.to_html(), "text/html"),
            "txt": (receipt.to_text(), "text/plain"),
            "json": (receipt.to_json(), "application/json"),
        }
        content, media_type = renderers[format]
        download_name = f"{base_name}.ghostmark-receipt.{format}"

        # PlainTextResponse for all three: it sends the string as-is with no
        # re-serialization, which matters for JSON (json.dumps already ran
        # inside receipt.to_json() -- re-encoding via JSONResponse would
        # just redundantly round-trip it).
        return PlainTextResponse(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    @app.delete("/api/session/{session_id}")
    def delete_session(session_id: str) -> dict[str, bool]:
        store.drop(session_id)
        return {"ok": True}

    return app
