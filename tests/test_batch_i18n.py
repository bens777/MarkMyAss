"""/batch localisation: the paid batch page reuses the site's single i18n
system (i18n.js resolver + shared i18n-fr.js dictionary + i18n-apply.js) and
every visible text exists in both English and French.

Static checks run everywhere; the resolver checks run the real JavaScript
under Node and are skipped when Node is unavailable (same harness as
tests/test_i18n.py)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from html import unescape
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "ghostmark" / "web" / "static"
BATCH_HTML = (STATIC / "batch.html").read_text(encoding="utf-8")
BATCH_JS = (STATIC / "batch.js").read_text(encoding="utf-8")
I18N_FR_SRC = (STATIC / "i18n-fr.js").read_text(encoding="utf-8")
I18N_APPLY_SRC = (STATIC / "i18n-apply.js").read_text(encoding="utf-8")
I18N_JS = STATIC / "i18n.js"
BATCH_PY = (ROOT / "src" / "ghostmark" / "web" / "batch.py").read_text(encoding="utf-8")

_NODE = shutil.which("node")
_needs_node = pytest.mark.skipif(_NODE is None, reason="Node.js not available to run the JS resolver")


def _fr_dict() -> dict[str, str]:
    """The shared dictionary, parsed from the `var dict = {...}` block."""

    block = I18N_FR_SRC[I18N_FR_SRC.index("var dict = {"): I18N_FR_SRC.index("var reprocessProfilesFr")]
    return dict(re.findall(r'"([\w.]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', block))


def _batch_markers() -> dict[str, str]:
    """data-i18n key -> English source text (inner HTML) in batch.html."""

    out = {}
    for m in re.finditer(r'<(\w+)[^>]*\sdata-i18n="([^"]+)"[^>]*>(.*?)</\1>', BATCH_HTML, re.S):
        out[m.group(2)] = m.group(3).strip()
    for spec in re.findall(r'data-i18n-attr="([^"]+)"', BATCH_HTML):
        for pair in spec.split(";"):
            if ":" in pair:
                out[pair.split(":", 1)[1].strip()] = ""
    return out


def _strip(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", html)).strip()


def _config(tmp_path) -> WebConfig:
    return WebConfig(
        mode="hosted", base_path="/", public_url="https://markmyass.test", session_ttl_seconds=600,
        rate_limit_per_minute=1000, max_concurrent_jobs=4, processing_timeout_seconds=30, max_upload_mb=10,
        stats_db_path=str(tmp_path / "stats.db"), batch_enabled=True, commerce_db_path=str(tmp_path / "commerce.db"),
    )


class _Gateway:
    def create_checkout_session(self, **kwargs):
        return "https://checkout.stripe.test/session"

    def retrieve_session(self, session_id):
        return None


# --- wiring: same system as the homepage --------------------------------------------------


def test_batch_page_uses_the_site_locale_engine_and_switcher():
    assert BATCH_HTML.startswith('<!doctype html>\n<html lang="en-US">')
    head = BATCH_HTML.split("</head>")[0]
    assert 'src="static/theme-init.js"' in head and 'src="static/i18n.js"' in head
    body = BATCH_HTML.split("<body>")[1]
    order = [body.index('src="static/i18n-fr.js"'), body.index('src="static/i18n-apply.js"'), body.index('src="static/batch.js"')]
    assert order == sorted(order), "dictionary, apply script, then batch.js -- same order as the homepage"
    # The existing FR | EN switcher, wired by i18n-apply.js, is on the page.
    assert 'data-lang-set="fr-FR"' in BATCH_HTML and 'data-lang-set="en-US"' in BATCH_HTML
    assert BATCH_HTML.count("data-lang-set=") == 2
    assert "data-lang-set" in I18N_APPLY_SRC and "setLocale" in I18N_APPLY_SRC
    # No second translation system: batch.js never hard-codes French statics.
    assert "innerHTML =\n      \"" not in BATCH_JS
    assert ".textContent = \"" not in BATCH_JS  # static copy comes from the DOM/dictionary only
    assert 'window.MarkMyAss.dict' in I18N_FR_SRC and "MMA.dict" in BATCH_JS


def test_batch_page_served_with_switcher_and_lang_attribute(tmp_path, monkeypatch):
    monkeypatch.setattr("ghostmark.web.batch.tempfile.gettempdir", lambda: str(tmp_path))
    with TestClient(create_app(_config(tmp_path), batch_gateway=_Gateway())) as client:
        html = client.get("/batch").text
    assert '<html lang="en-US">' in html
    assert 'data-lang-set="fr-FR"' in html and 'data-lang-set="en-US"' in html
    assert 'data-i18n="batch.meta.title"' in html


def test_title_marker_is_honoured_by_the_shared_apply_script():
    assert 'title[data-i18n]' in I18N_APPLY_SRC
    assert '<title data-i18n="batch.meta.title">' in BATCH_HTML


# --- coverage: every visible text exists in FR and EN ---------------------------------------


def test_every_batch_marker_has_a_french_translation_that_differs_from_english():
    fr = _fr_dict()
    markers = _batch_markers()
    assert markers, "batch.html has no data-i18n markers"
    missing = sorted(k for k in markers if k not in fr)
    assert not missing, f"French missing for: {missing}"
    for key, en in markers.items():
        if not en:  # attribute markers (lang.switch.aria) are shared with the homepage
            continue
        assert fr[key].strip(), key
        assert _strip(fr[key]) != _strip(en), f"{key}: French equals English source"
        # offer placeholders must survive translation so batch.js can fill them.
        for cls in ("offer-range", "offer-price", "offer-max-file", "offer-max-total", "offer-window", "offer-zip-hours"):
            assert (cls in en) == (cls in fr[key]), f"{key}: placeholder {cls} lost in translation"


def test_every_api_error_code_has_a_french_text():
    fr = _fr_dict()
    codes = set(re.findall(r'_err\(\d+, "([a-z_]+)"', BATCH_PY))
    assert codes, "no error codes found in batch.py"
    missing = sorted(c for c in codes if f"batch.err.{c}" not in fr)
    assert not missing, f"French missing for API error codes: {missing}"
    assert "x-batch-error" in BATCH_JS and 'batch.err.' in BATCH_JS


def test_runtime_strings_have_distinct_french_and_english_variants():
    pairs = re.findall(r'\bt\(\s*(`[^`]*`|"[^"]*")\s*,\s*(`[^`]*`|"[^"]*")\s*\)', BATCH_JS)
    assert len(pairs) >= 10
    for en, fr in pairs:
        assert en.strip('`"').strip() and fr.strip('`"').strip()
        assert en != fr, f"runtime string not translated: {en}"


def test_no_french_in_english_source_and_no_english_left_in_french():
    fr = _fr_dict()
    en_text = _strip(BATCH_HTML.split("<body>")[1]).lower()
    for key in _batch_markers():
        value = _strip(fr.get(key, "")).lower()
        if value and value not in ("fr", "en"):
            assert value not in en_text, f"French text of {key} present in the English page"
    # Typical French-only tokens never appear in the English source...
    for word in (" vos ", " fichiers", " paiement", "téléch", " lot de "):
        assert word not in en_text, word
    # ...and typical English-only tokens never appear in the French strings.
    for word in (" your ", " files ", "payment ", "download", "the zip"):
        for key in _batch_markers():
            if key.startswith("batch."):
                assert word not in _strip(fr[key]).lower(), f"{key}: English left in French ({word!r})"


def test_stripe_checkout_receives_the_chosen_language():
    assert 'locale="fr" if locale == "fr" else "en"' in BATCH_PY
    assert 'locale: isFr ? "fr" : "en"' in BATCH_JS


# --- resolver: browser language and the remembered manual choice ---------------------------


def _resolve(cases):
    script = (
        "const {resolveLocale} = require(process.argv[1]);"
        "const cases = JSON.parse(process.argv[2]);"
        "console.log(JSON.stringify(cases.map(c => resolveLocale(c[0], c[1]))));"
    )
    out = subprocess.run([_NODE, "-e", script, str(I18N_JS), json.dumps(cases)], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout.strip())


@_needs_node
def test_french_browser_without_saved_choice_gets_french():
    assert _resolve([["fr", None], ["fr-FR", None], ["fr-CA", None], ["fr-BE", None]]) == ["fr-FR"] * 4


@_needs_node
def test_non_french_browser_without_saved_choice_gets_english():
    assert _resolve([["en-US", None], ["en-GB", None], ["de-DE", None], ["es-ES", None], ["ja-JP", None], ["", None]]) == ["en-US"] * 6


@_needs_node
def test_saved_manual_choice_wins_over_browser_language():
    assert _resolve([["de-DE", "fr-FR"], ["fr-FR", "en-US"], ["fr-CA", "en-US"], ["en-US", "fr-FR"]]) == ["fr-FR", "en-US", "en-US", "fr-FR"]


def test_switching_on_batch_uses_the_same_storage_key_as_the_site():
    i18n_src = I18N_JS.read_text(encoding="utf-8")
    assert 'STORAGE_KEY = "markmyass-language"' in i18n_src
    # The switcher persists through MarkMyAss.setLocale (localStorage + reload),
    # which i18n-apply.js wires to every [data-lang-set] button -- on /batch too.
    assert "localStorage.setItem(STORAGE_KEY, loc)" in i18n_src
    assert "btn.addEventListener(\"click\"" in I18N_APPLY_SRC and "MMA.setLocale(loc)" in I18N_APPLY_SRC
