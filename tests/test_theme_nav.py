"""Theme default/toggle + responsive header: server-rendered guarantees.

Dark is the canonical MarkMyAss identity: a fresh visitor gets dark
regardless of prefers-color-scheme; light is an explicit, persisted
choice (localStorage "markmyass-theme") applied before first paint by
static/theme-init.js. The mobile header keeps the Moseisley CTA and the
theme toggle OUTSIDE the hamburger.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig

STATIC = Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static"


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/",
        public_url="https://markmyass.com",
        session_ttl_seconds=480,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=10,
    )
    base.update(overrides)
    return WebConfig(**base)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(_config()))


# --- Theme selection ---------------------------------------------------------------------


def test_css_dark_is_default_and_light_is_explicit_opt_in():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    # Strip comments so prose explaining the policy can't trip the check.
    css_rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # Light palette only via the data-theme attribute, never via system pref.
    assert ':root[data-theme="light"]' in css_rules
    assert "prefers-color-scheme" not in css_rules
    # Reduced-motion handling must survive the theme rework.
    assert "prefers-reduced-motion" in css_rules
    # Dark tokens are the :root default.
    root_block = css.split(":root {", 1)[1].split("}", 1)[0]
    assert "--bg: #0e1b33" in root_block


def test_theme_init_runs_before_stylesheet_on_homepage_and_articles(client):
    for path in ("/", "/lab", "/skill", "/claude-watermark-remover"):
        html = client.get(path).text
        init = html.find("static/theme-init.js")
        css = html.find("static/style.css")
        assert 0 < init < css, f"{path}: theme-init.js must load before the stylesheet"


def test_theme_init_defaults_dark_and_uses_storage_key():
    js = (STATIC / "theme-init.js").read_text(encoding="utf-8")
    js_code = re.sub(r"^\s*//.*$", "", js, flags=re.M)  # strip comment prose
    assert "markmyass-theme" in js_code
    assert '"dark"' in js_code
    # Only an explicit "light" choice selects light; never matchMedia.
    assert "matchMedia" not in js_code and "prefers-color-scheme" not in js_code


def test_toggle_button_present_with_accessible_labels(client):
    html = client.get("/").text
    assert 'id="theme-toggle"' in html
    assert 'aria-label="Switch to light mode"' in html  # dark is the default state
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '"Switch to light mode"' in js and '"Switch to dark mode"' in js
    assert 'localStorage.setItem("markmyass-theme"' in js


# --- Responsive header -------------------------------------------------------------------


def test_secondary_nav_grouped_with_cta_and_toggle_outside(client):
    html = client.get("/").text
    nav_links = re.search(r'<div id="nav-links" class="nav-links">(.*?)</div>', html, re.S)
    assert nav_links, "secondary nav group missing"
    inner = nav_links.group(1)
    for href in ("#input-section", "skill", "lab", "benchmarks", "run-ai-locally"):
        assert f'href="{href}"' in inner
    assert "github.com/bens777/MarkMyAss" in inner
    # CTA and theme toggle live OUTSIDE the collapsible group.
    assert "moseisley.sh" not in inner
    assert "theme-toggle" not in inner
    assert "nav-burger" not in inner


def test_burger_button_aria_wiring(client):
    html = client.get("/").text
    assert 'id="nav-burger"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="nav-links"' in html
    assert 'aria-label="Open navigation"' in html
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '"Close navigation"' in js and '"Open navigation"' in js


def test_moseisley_cta_url_and_label_unchanged(client):
    html = client.get("/").text
    assert (
        'class="nav-cta" href="https://moseisley.sh/?utm_source=markmyass&amp;'
        "utm_medium=navbar&amp;utm_campaign=acquisition" in html
    )
    # Short visible label on narrow screens, full accessible name always.
    m = re.search(r'<a class="nav-cta"[^>]*aria-label="([^"]*)"', html)
    assert m and m.group(1) == "Get your AI crew"
    assert "nav-cta-short" in html and "AI crew" in html
