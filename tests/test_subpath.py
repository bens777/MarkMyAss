"""Reverse-proxy subpath support: relative URLs + <base href> injection.

The production deployment reverse-proxies /ghostmark/* to this app with
the prefix stripped (see deploy/Caddyfile.snippet), so the app itself
always sees unprefixed paths ("/", "/api/...", "/static/..."). What has
to change for the subpath to work end-to-end is the HTML the browser
receives: it must never contain a root-absolute link like "/static/..."
that would resolve to the wrong place once the page's real URL is
"https://host/ghostmark/". These tests catch exactly that class of bug.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="local",
        base_path="/",
        public_url="https://moseisley.sh/ghostmark",
        session_ttl_seconds=720,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=50,
    )
    base.update(overrides)
    return WebConfig(**base)


def test_root_mode_base_href_is_slash():
    client = TestClient(create_app(_config(base_path="/")))
    resp = client.get("/")
    assert resp.status_code == 200
    assert '<base href="/">' in resp.text


def test_subpath_mode_base_href_is_prefixed():
    client = TestClient(create_app(_config(mode="hosted", base_path="/ghostmark/")))
    resp = client.get("/")
    assert resp.status_code == 200
    assert '<base href="/ghostmark/">' in resp.text


def test_no_root_absolute_asset_or_script_links():
    """Every href/src in the shipped HTML must be relative, not root-absolute.

    A root-absolute link (starting with "/") would bypass the reverse
    proxy's path prefix and 404 (or hit an unrelated route) once the page
    is actually served at /ghostmark/.
    """

    client = TestClient(create_app(_config(mode="hosted", base_path="/ghostmark/")))
    html = client.get("/").text
    # The <base> tag is meant to be root-absolute -- it's what makes every
    # OTHER relative link resolve correctly. Strip it before scanning.
    html_without_base = re.sub(r"<base[^>]*>", "", html)

    for attr in ("href", "src"):
        for match in re.finditer(rf'{attr}="([^"]*)"', html_without_base):
            value = match.group(1)
            if value.startswith(("http://", "https://", "#", "mailto:")):
                continue
            assert not value.startswith("/"), f"{attr}=\"{value}\" is root-absolute and will bypass /ghostmark/"


def test_config_endpoint_reflects_base_path_and_mode():
    client = TestClient(create_app(_config(mode="hosted", base_path="/ghostmark/", max_upload_mb=20)))
    resp = client.get("/api/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "hosted"
    assert body["base_path"] == "/ghostmark/"
    assert body["max_upload_mb"] == 20


def test_app_js_uses_only_relative_api_paths():
    """The frontend script must never fetch a root-absolute /api/... URL."""

    from pathlib import Path

    app_js = (Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert '"/api/' not in app_js
    assert "fetch(\"/" not in app_js
