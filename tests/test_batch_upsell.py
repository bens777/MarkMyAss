"""Homepage upsell for the paid batch feature.

A single link styled as a third tab, next to "Upload File", pointing to
/batch. It must be hidden unless /api/config reports batch_enabled=true,
translated through the site's one i18n system, and never touch the free
single-file flow.

Three layers:

1. Static checks (always run): markup, dictionary, the app.js switch.
2. Server checks (always run): what the homepage and /api/config serve with
   the feature on and off.
3. Browser checks (skipped without Playwright + its Chromium): the real page
   in an isolated headless Chromium -- hidden/visible, FR/EN wording from
   browser language and from the remembered choice, link target, and the
   desktop row / mobile wrap layout.
"""

from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "ghostmark" / "web" / "static"
INDEX_HTML = (STATIC / "index.html").read_text(encoding="utf-8")
APP_JS = (STATIC / "app.js").read_text(encoding="utf-8")
STYLE_CSS = (STATIC / "style.css").read_text(encoding="utf-8")
I18N_FR_SRC = (STATIC / "i18n-fr.js").read_text(encoding="utf-8")

EN_TEXT = "Process 2–50 files — €1.99"
FR_TEXT = "Traiter 2 à 50 fichiers — 1,99 €"
UPSELL_RE = re.compile(r'<a\s+id="tab-batch"[^>]*>(.*?)</a>', re.S)


def _upsell_tag() -> str:
    m = re.search(r'<a\s+id="tab-batch"[^>]*>', INDEX_HTML)
    assert m, "homepage has no #tab-batch upsell link"
    return m.group(0)


def _fr_dict() -> dict[str, str]:
    block = I18N_FR_SRC[I18N_FR_SRC.index("var dict = {"): I18N_FR_SRC.index("var reprocessProfilesFr")]
    return dict(re.findall(r'"([\w.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', block))


class _Gateway:
    def create_checkout_session(self, **kwargs):
        return "https://checkout.stripe.test/session"

    def retrieve_session(self, session_id):
        return None


def _config(tmp_path, *, enabled: bool) -> WebConfig:
    return WebConfig(
        mode="hosted", base_path="/", public_url="https://markmyass.test", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
        stats_db_path=str(tmp_path / "stats.db"), batch_enabled=enabled, commerce_db_path=str(tmp_path / "commerce.db"),
    )


# --- 1. static ------------------------------------------------------------------------------


def test_upsell_sits_next_to_the_upload_tab_and_links_to_batch():
    tabs = re.search(r'<div class="tabs">(.*?)</div>', INDEX_HTML, re.S).group(1)
    assert 'id="tab-file"' in tabs and 'id="tab-batch"' in tabs
    assert tabs.index('id="tab-file"') < tabs.index('id="tab-batch"')
    # Only one upsell on the page, and it is a plain link to the batch page
    # (relative, like the nav link, so <base href> keeps it on /batch).
    assert INDEX_HTML.count('id="tab-batch"') == 1
    tag = _upsell_tag()
    assert 'href="batch"' in tag
    assert UPSELL_RE.search(INDEX_HTML).group(1).strip() == EN_TEXT


def test_upsell_is_hidden_in_the_markup_and_switched_by_batch_enabled():
    classes = re.search(r'class="([^"]+)"', _upsell_tag()).group(1).split()
    assert "batch-only" in classes and "hidden" in classes, classes
    assert "tab" in classes and "tab-upsell" in classes
    # app.js reveals every .batch-only element from /api/config.batch_enabled,
    # and only from it (no other code path toggles the class).
    assert 'querySelectorAll(".batch-only").forEach((elm) => elm.classList.toggle("hidden", !config.batch_enabled))' in APP_JS
    assert APP_JS.count("batch-only") == 1
    assert ".hidden { display: none !important; }" in STYLE_CSS


def test_upsell_uses_the_shared_dictionary_with_the_exact_wording():
    assert 'data-i18n="tool.tab.batch"' in _upsell_tag()
    assert _fr_dict()["tool.tab.batch"] == FR_TEXT
    # No second translation mechanism for it.
    assert FR_TEXT not in INDEX_HTML and FR_TEXT not in APP_JS


def test_upsell_wraps_onto_its_own_line_on_small_screens():
    assert ".tabs { flex-wrap: wrap; }" in STYLE_CSS
    mobile = re.search(r"@media \(max-width: 640px\) \{[^@]*?\.tab-upsell \{ flex-basis: 100%; \}", STYLE_CSS)
    assert mobile, "no mobile rule making the upsell take a full row"
    # The free tabs' sizing changes only while the upsell is actually shown.
    assert ".tabs:has(.tab-upsell:not(.hidden)) .tab { flex: 1 1 auto; }" in STYLE_CSS


# --- 2. server ------------------------------------------------------------------------------


def test_feature_off_serves_the_upsell_hidden_and_no_batch_page(tmp_path):
    with TestClient(create_app(_config(tmp_path, enabled=False))) as client:
        html = client.get("/").text
        assert client.get("/api/config").json()["batch_enabled"] is False
        assert client.get("/batch").status_code == 404
    assert "hidden" in re.search(r'<a\s+id="tab-batch"[^>]*class="([^"]+)"', html).group(1).split()
    assert EN_TEXT in html


def test_feature_on_serves_config_true_and_a_live_batch_page(tmp_path, monkeypatch):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    with TestClient(create_app(_config(tmp_path, enabled=True), batch_gateway=_Gateway())) as client:
        html = client.get("/").text
        assert client.get("/api/config").json()["batch_enabled"] is True
        assert client.get("/batch").status_code == 200
        # The free single-file flow is untouched by the upsell.
        assert client.post("/api/inspect/text", json={"text": "hello"}).status_code == 200
    assert 'href="batch"' in _upsell_tag() and 'id="tab-batch"' in html


# --- 3. browser (isolated Playwright Chromium, never the user's browser) --------------------

try:  # pragma: no cover - availability differs per machine
    import uvicorn
    from playwright.sync_api import Error as _PWError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

_needs_browser = pytest.mark.skipif(sync_playwright is None, reason="Playwright (and uvicorn) not installed")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    """The real app under uvicorn on a loopback port, in a thread."""

    def __init__(self, config: WebConfig, gateway=None):
        self.port = _free_port()
        app = create_app(config, batch_gateway=gateway)
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self):
        self._thread.start()
        deadline = time.time() + 15
        while not self._server.started:
            assert time.time() < deadline, "uvicorn did not start"
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        self._server.should_exit = True
        self._thread.join(timeout=10)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"


@pytest.fixture(scope="module")
def browser():
    if sync_playwright is None:
        pytest.skip("Playwright not installed")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()  # isolated, project-owned instance
        except _PWError as exc:  # browser binary missing
            pytest.skip(f"Playwright Chromium unavailable: {exc.message.splitlines()[0]}")
        yield b
        b.close()  # closes ONLY this instance


def _open(browser, url, *, locale, width=1400, saved=None):
    ctx = browser.new_context(locale=locale, viewport={"width": width, "height": 900}, color_scheme="light")
    if saved:
        ctx.add_init_script(f'try {{ localStorage.setItem("markmyass-language", "{saved}"); }} catch (e) {{}}')
    page = ctx.new_page()
    page.goto(url)
    page.wait_for_function("() => window.MarkMyAss && document.documentElement.lang !== ''")
    # app.js applies /api/config asynchronously; wait for the nav/upsell switch to settle.
    page.wait_for_function("() => document.querySelectorAll('.hosted-only.hidden').length === 0")
    return ctx, page


@_needs_browser
def test_browser_hides_the_upsell_when_batch_is_disabled(tmp_path, browser):
    with _Server(_config(tmp_path, enabled=False)) as srv:
        ctx, page = _open(browser, srv.url, locale="fr-FR")
        try:
            assert page.evaluate("() => fetch('api/config').then(r => r.json()).then(c => c.batch_enabled)") is False
            upsell = page.locator("#tab-batch")
            assert upsell.count() == 1 and not upsell.is_visible()
            assert page.locator("#tab-file").is_visible()
        finally:
            ctx.close()


@_needs_browser
@pytest.mark.parametrize(
    ("locale", "saved", "expected"),
    [("fr-FR", None, FR_TEXT), ("en-US", None, EN_TEXT), ("de-DE", None, EN_TEXT), ("en-US", "fr-FR", FR_TEXT), ("fr-FR", "en-US", EN_TEXT)],
)
def test_browser_shows_the_translated_upsell_when_batch_is_enabled(tmp_path, monkeypatch, browser, locale, saved, expected):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    with _Server(_config(tmp_path, enabled=True), gateway=_Gateway()) as srv:
        ctx, page = _open(browser, srv.url, locale=locale, saved=saved)
        try:
            upsell = page.locator("#tab-batch")
            upsell.wait_for(state="visible")
            assert upsell.inner_text().strip() == expected
            assert page.locator("#tab-file").inner_text().strip() in ("Upload File", "Téléverser un fichier")
            assert upsell.evaluate("a => new URL(a.href).pathname") == "/batch"
            with page.expect_navigation():
                upsell.click()
            assert page.url.rstrip("/").endswith("/batch")
        finally:
            ctx.close()


@_needs_browser
@pytest.mark.parametrize(("width", "same_row"), [(1400, True), (400, False)])
def test_browser_layout_desktop_row_and_mobile_wrap(tmp_path, monkeypatch, browser, width, same_row):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    with _Server(_config(tmp_path, enabled=True), gateway=_Gateway()) as srv:
        ctx, page = _open(browser, srv.url, locale="fr-FR", width=width)
        try:
            upsell = page.locator("#tab-batch")
            upsell.wait_for(state="visible")
            tab = page.locator("#tab-file").bounding_box()
            box = upsell.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= width, "upsell overflows the viewport"
            if same_row:
                assert abs(box["y"] - tab["y"]) < 2, "desktop: upsell should sit on the tabs row"
            else:
                assert box["y"] >= tab["y"] + tab["height"] - 1, "mobile: upsell should wrap below the tabs"
                assert box["width"] >= tab["width"] * 2, "mobile: upsell should take the full row"
            # Readable: the whole label fits in the box (no clipped text).
            assert upsell.evaluate("a => a.scrollWidth <= a.clientWidth + 1 && a.scrollHeight <= a.clientHeight + 1")
            # The tool card (tabs included) never widens past the viewport.
            assert page.locator("#input-section").evaluate("s => s.getBoundingClientRect().right <= window.innerWidth")
        finally:
            ctx.close()
