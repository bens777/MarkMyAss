"""Locale engine + French translation coverage for the web homepage.

Two kinds of test here:

1. Static structural checks (pure Python, always run): the language plumbing
   is wired into index.html (lang attribute default, script order, switcher),
   and -- critically -- the French set covers EVERY translatable marker so the
   fr-FR homepage is never partial ("no mixed-language UI").

2. Logic checks executed with Node (skipped if node is unavailable): the
   pure resolveLocale() function against the full spec table (fr-CA -> fr-FR,
   en-GB -> en-US, saved override wins, ...).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "src" / "ghostmark" / "web" / "static"
INDEX = STATIC / "index.html"
I18N_JS = STATIC / "i18n.js"
I18N_FR_JS = STATIC / "i18n-fr.js"
I18N_APPLY_JS = STATIC / "i18n-apply.js"

INDEX_HTML = INDEX.read_text(encoding="utf-8")
I18N_JS_SRC = I18N_JS.read_text(encoding="utf-8")
I18N_FR_SRC = I18N_FR_JS.read_text(encoding="utf-8")


# --- helpers ----------------------------------------------------------------------------


def _dom_i18n_keys() -> set[str]:
    """Every translation key referenced by index.html (content + attributes)."""
    keys = set(re.findall(r'data-i18n="([^"]+)"', INDEX_HTML))
    for spec in re.findall(r'data-i18n-attr="([^"]+)"', INDEX_HTML):
        for pair in spec.split(";"):
            if ":" in pair:
                keys.add(pair.split(":", 1)[1].strip())
    return keys


def _fr_dict_keys() -> set[str]:
    """Keys defined in the French dictionary object in i18n-fr.js.

    Parsed from the `var dict = { "key": ... }` block so the reprocess
    profile map (unquoted identifier keys) is not conflated with it.
    """
    start = I18N_FR_SRC.index("var dict = {")
    end = I18N_FR_SRC.index("var reprocessProfilesFr")
    block = I18N_FR_SRC[start:end]
    return set(re.findall(r'"([\w.]+)"\s*:', block))


# --- structural checks ------------------------------------------------------------------


def test_html_default_lang_is_en_us():
    assert '<html lang="en-US">' in INDEX_HTML


def test_locale_scripts_are_wired_in_order():
    # i18n.js loads in <head> (pre-paint, like theme-init).
    assert "static/i18n.js" in INDEX_HTML.split("</head>")[0]
    # The dictionary + apply script load before app.js at the end of body.
    i_fr = INDEX_HTML.index("static/i18n-fr.js")
    i_apply = INDEX_HTML.index("static/i18n-apply.js")
    i_app = INDEX_HTML.index("static/app.js")
    assert i_fr < i_apply < i_app


def test_storage_key_is_markmyass_language():
    assert '"markmyass-language"' in I18N_JS_SRC


def test_switcher_offers_exactly_the_two_locales():
    assert 'data-lang-set="fr-FR"' in INDEX_HTML
    assert 'data-lang-set="en-US"' in INDEX_HTML
    # No stray unsupported locale switch buttons.
    assert set(re.findall(r'data-lang-set="([^"]+)"', INDEX_HTML)) == {"fr-FR", "en-US"}


def test_no_mixed_language_ui_every_marker_has_french():
    """Every data-i18n / data-i18n-attr key in the homepage has a French
    translation, so switching to fr-FR can never leave a partial UI."""
    dom = _dom_i18n_keys()
    fr = _fr_dict_keys()
    missing = sorted(dom - fr)
    assert not missing, f"French translations missing for: {missing}"


def test_french_dict_has_no_orphan_keys():
    """Guard against dead dictionary entries drifting out of sync with the DOM."""
    dom = _dom_i18n_keys()
    fr = _fr_dict_keys()
    # meta.title is applied to document.title, not to a DOM marker.
    orphans = sorted(fr - dom - {"meta.title"})
    assert not orphans, f"French keys with no matching marker: {orphans}"


# --- Node-executed logic checks ---------------------------------------------------------

_NODE = shutil.which("node")
_needs_node = pytest.mark.skipif(_NODE is None, reason="Node.js not available to run the JS resolver")

# The full spec table: (navigator.language, saved choice) -> expected locale.
_RESOLVER_CASES = [
    ("fr-FR", None, "fr-FR"),
    ("fr-CA", None, "fr-FR"),
    ("fr-BE", None, "fr-FR"),
    ("fr-CH", None, "fr-FR"),
    ("fr", None, "fr-FR"),
    ("en-US", None, "en-US"),
    ("en-GB", None, "en-US"),
    ("de-DE", None, "en-US"),
    ("es-ES", None, "en-US"),
    ("it-IT", None, "en-US"),
    ("pt-BR", None, "en-US"),
    ("ja-JP", None, "en-US"),
    ("", None, "en-US"),
    (None, None, "en-US"),
    # A saved manual choice always overrides browser detection.
    ("de-DE", "fr-FR", "fr-FR"),
    ("fr-FR", "en-US", "en-US"),
    # An invalid/legacy saved value is ignored -> fall back to detection.
    ("fr-CA", "fr-CA", "fr-FR"),
    ("de-DE", "garbage", "en-US"),
]


def _run_node_resolver(cases) -> list[str]:
    payload = json.dumps([[nav, saved] for nav, saved, _ in cases])
    script = (
        "const {resolveLocale} = require(process.argv[1]);"
        "const cases = JSON.parse(process.argv[2]);"
        "console.log(JSON.stringify(cases.map(c => resolveLocale(c[0], c[1]))));"
    )
    out = subprocess.run(
        [_NODE, "-e", script, str(I18N_JS), payload],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout.strip())


@_needs_node
def test_resolve_locale_matches_spec_table():
    results = _run_node_resolver(_RESOLVER_CASES)
    got = {(nav, saved): res for (nav, saved, _), res in zip(_RESOLVER_CASES, results, strict=True)}
    expected = {(nav, saved): exp for nav, saved, exp in _RESOLVER_CASES}
    assert got == expected


@_needs_node
def test_fr_dict_loads_and_covers_dom_in_node():
    """Cross-check coverage by actually loading the dict in Node (not regex)."""
    script = (
        "const {dict} = require(process.argv[1]);"
        "console.log(JSON.stringify(Object.keys(dict)));"
    )
    out = subprocess.run(
        [_NODE, "-e", script, str(I18N_FR_JS)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    fr_keys = set(json.loads(out.stdout.strip()))
    missing = sorted(_dom_i18n_keys() - fr_keys)
    assert not missing, f"French translations missing for: {missing}"
