"""Homepage: new positioning copy, nav links, Explain/receipt UI scaffolding present."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/ghostmark/",
        public_url="https://moseisley.sh/ghostmark",
        session_ttl_seconds=720,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=20,
    )
    base.update(overrides)
    return WebConfig(**base)


def test_homepage_has_new_positioning_copy():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert "Proof, not promises." in html
    assert "shows exactly what it removed" in html
    assert '100% undetectable' in html  # inside the honesty-note disclaimer


def test_homepage_trust_bar_matches_spec():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    for item in ["Free", "Open source", "No account", "Independent verification", "Download your cleaned file"]:
        assert item in html


def test_homepage_links_to_lab_and_benchmarks_and_run_local():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'href="lab"' in html
    assert 'href="benchmarks"' in html
    assert 'href="run-ai-locally"' in html


def test_homepage_moseisley_copy_updated():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert "An open-source project by" in html
    assert "Meet Moseisley" in html
    assert "Explore Moseisley" in html


def test_homepage_moseisley_links_point_to_moseisley_with_utm_attribution():
    """Both Moseisley links (top attribution, bottom CTA) must point to the
    real moseisley.sh domain (never a lookalike/typo domain) and carry
    simple, privacy-compatible UTM query params for attribution -- no
    tracking pixels, no third-party scripts, no cookies."""

    client = TestClient(create_app(_config()))
    html = client.get("/").text
    # Matches only the two outbound "visit Moseisley" links (bare domain +
    # query string) -- NOT this test fixture's own self-referential
    # canonical/OG URL, which happens to also live on the moseisley.sh
    # domain (https://moseisley.sh/ghostmark, a path, not a query string)
    # when public_url is configured for the subpath deployment style.
    moseisley_links = re.findall(r'href="(https://moseisley\.sh\?[^"]*)"', html)
    assert len(moseisley_links) == 2
    for link in moseisley_links:
        assert link.startswith("https://moseisley.sh?")
        assert "utm_source=ghostmark" in link
        assert "utm_medium=referral" in link


def test_homepage_never_calls_moseisley_promo_a_popup_or_interstitial():
    """Sanity check the promo stays inline copy, not a modal/popup pattern."""

    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert "modal" not in html.lower()
    assert "popup" not in html.lower()
    assert "countdown" not in html.lower()


def test_homepage_has_explain_panel_scaffolding():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'id="explain-panel"' in html
    assert 'id="explain-list"' in html
    assert "What this means" in html


def test_homepage_has_receipt_download_scaffolding():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'id="receipt-downloads"' in html
    assert 'id="receipt-json"' in html
    assert 'id="receipt-html"' in html
    assert 'id="receipt-txt"' in html
    assert "Verification Receipt" in html


def test_homepage_statistical_watermark_note_links_to_lab():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'href="lab/claude-watermark"' in html


def test_app_js_defines_explanations_for_every_metadata_detector():
    from pathlib import Path

    app_js = (Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    for detector in ["unicode", "exif", "xmp", "iptc", "png_text", "pdf_info", "pdf_xmp", "c2pa"]:
        assert f"{detector}:" in app_js, f"missing Explain copy for detector {detector!r}"


def test_app_js_wires_verdict_states_including_new_ones():
    from pathlib import Path

    app_js = (Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    for verdict in ["verified_clean", "partial", "unverified", "not_applicable", "failed"]:
        assert verdict in app_js
