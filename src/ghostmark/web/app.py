"""FastAPI application for the GhostMark local web UI.

Design constraints enforced here:
  - No route ever proxies or fetches anything over the network.
  - Uploaded files are stored only in a per-session temp directory under the
    OS temp dir, with a randomized session id and a sanitized filename.
  - Sessions (and their temp files) are cleaned up on delete and on
    process exit -- nothing lingers on disk after the server stops.
  - The caller (ghostmark.cli.ui) is responsible for binding to
    127.0.0.1 only; this module never chooses the bind address itself.
"""

from __future__ import annotations

import atexit
import secrets
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ghostmark import __version__
from ghostmark.cleaner import clean_file, clean_text_content
from ghostmark.inspector import inspect_file, inspect_text
from ghostmark.security import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    check_size,
    check_supported,
    sanitize_filename,
)
from ghostmark.verifier import verify_file, verify_text

STATIC_DIR = Path(__file__).parent / "static"


class _Session:
    def __init__(self, kind: str) -> None:
        self.kind = kind  # "text" | "file"
        self.workdir = Path(tempfile.mkdtemp(prefix="ghostmark-session-"))
        self.text: str | None = None
        self.cleaned_text: str | None = None
        self.original_path: Path | None = None
        self.cleaned_path: Path | None = None
        self.original_name: str = ""

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


class _SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

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

    def cleanup_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.cleanup()


class TextIn(BaseModel):
    text: str


def create_app() -> FastAPI:
    app = FastAPI(title="GhostMark", version=__version__, docs_url=None, redoc_url=None)
    store = _SessionStore()
    atexit.register(store.cleanup_all)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        index_path = STATIC_DIR / "index.html"
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "local_only": True}

    @app.post("/api/inspect/text")
    def inspect_text_route(body: TextIn) -> dict[str, Any]:
        session_id, session = store.create("text")
        session.text = body.text
        report = inspect_text(body.text)
        return {"session_id": session_id, "report": report.to_dict()}

    @app.post("/api/inspect/file")
    async def inspect_file_route(file: UploadFile = File(...)) -> dict[str, Any]:
        safe_name = sanitize_filename(file.filename or "upload")
        try:
            check_supported(safe_name)
        except UnsupportedFileTypeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        data = await file.read()
        try:
            check_size(len(data))
        except FileTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc

        session_id, session = store.create("file")
        session.original_name = safe_name
        session.original_path = session.workdir / f"original{Path(safe_name).suffix.lower()}"
        session.original_path.write_bytes(data)

        try:
            report = inspect_file(session.original_path)
        except Exception as exc:  # noqa: BLE001 - untrusted file content must never crash the server
            store.drop(session_id)
            raise HTTPException(status_code=400, detail=f"Could not inspect file: {exc}") from exc

        return {"session_id": session_id, "report": report.to_dict()}

    @app.post("/api/clean/{session_id}")
    def clean_route(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        if session.kind == "text":
            if session.text is None:
                raise HTTPException(status_code=400, detail="No text in this session.")
            cleaned, result = clean_text_content(session.text)
            session.cleaned_text = cleaned
            payload = result.to_dict()
            payload["cleaned_text"] = cleaned
            return payload

        if session.original_path is None:
            raise HTTPException(status_code=400, detail="No file in this session.")
        try:
            result = clean_file(session.original_path)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"Could not clean file: {exc}") from exc
        session.cleaned_path = Path(result.output)
        return result.to_dict()

    @app.post("/api/verify/{session_id}")
    def verify_route(session_id: str) -> dict[str, Any]:
        session = store.get(session_id)
        if session.kind == "text":
            if session.text is None or session.cleaned_text is None:
                raise HTTPException(status_code=400, detail="Run clean before verify.")
            result = verify_text(session.text, session.cleaned_text)
            return result.to_dict()

        if session.original_path is None or session.cleaned_path is None:
            raise HTTPException(status_code=400, detail="Run clean before verify.")
        result = verify_file(session.original_path, session.cleaned_path)
        return result.to_dict()

    @app.get("/api/download/{session_id}")
    def download_route(session_id: str) -> FileResponse:
        session = store.get(session_id)
        if session.kind != "file" or session.cleaned_path is None or not session.cleaned_path.exists():
            raise HTTPException(status_code=400, detail="No cleaned file available for this session.")
        stem = Path(session.original_name).stem
        suffix = Path(session.original_name).suffix
        download_name = f"{stem}.ghostmark{suffix}"
        return FileResponse(session.cleaned_path, filename=download_name, media_type="application/octet-stream")

    @app.delete("/api/session/{session_id}")
    def delete_session(session_id: str) -> dict[str, bool]:
        store.drop(session_id)
        return {"ok": True}

    return app
