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


def test_homepage_moseisley_acquisition_placements_present():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert "An open-source project by" in html      # hosted top attribution
    assert "Get your AI crew" in html               # navbar chip
    assert "From one tool to a whole crew" in html  # homepage section
    assert "Want the whole crew?" in html           # post-verify card
    assert "MarkMyAss is built by" in html          # footer attribution
    # Value first, Moseisley second: the post-verify card starts hidden
    # and is only revealed after the user has their verified result.
    assert 'id="moseisley-cta" class="moseisley-cta hidden"' in html


def test_homepage_moseisley_links_point_to_moseisley_with_utm_attribution():
    """Every Moseisley link must point to the real moseisley.sh domain
    (never a lookalike/typo domain) and carry simple, privacy-compatible
    UTM query params with a DISTINCT utm_medium per placement -- no
    tracking pixels, no third-party scripts, no cookies."""

    client = TestClient(create_app(_config()))
    html = client.get("/").text
    # Matches only outbound "visit Moseisley" links (domain root + query
    # string) -- NOT this test fixture's own self-referential canonical/OG
    # URL (https://moseisley.sh/ghostmark, a path without a query string).
    moseisley_links = re.findall(r'href="(https://moseisley\.sh/\?[^"]*)"', html)
    # top attribution + navbar + homepage section (inline link + button) +
    # post-verify card + footer
    assert len(moseisley_links) >= 5
    media = set()
    for link in moseisley_links:
        assert link.startswith("https://moseisley.sh/?")
        assert "utm_source=markmyass" in link
        assert "utm_campaign=" in link
        m = re.search(r"utm_medium=([a-z_]+)", link)
        assert m, link
        media.add(m.group(1))
    assert {"navbar", "homepage", "product", "footer", "top"} <= media


def test_magicconnect_is_a_single_discreet_footer_link_only():
    """MagicConnect is a secondary ecosystem link: exactly one footer
    occurrence, tracked URL, no button/CTA treatment, and Moseisley
    stays the primary acquisition path (strictly more placements)."""

    client = TestClient(create_app(_config()))
    html = client.get("/").text
    links = re.findall(r'href="(https://magicconnect\.ai/[^"]*)"', html)
    assert links == [
        "https://magicconnect.ai/?utm_source=markmyass&amp;utm_medium=footer&amp;utm_campaign=ecosystem"
    ]
    footer = html.split("<footer>", 1)[1]
    assert "magicconnect.ai" in footer  # in the footer...
    assert "magicconnect" not in html.split("<footer>", 1)[0].lower()  # ...and ONLY there
    # No CTA styling: the link is a plain footer-ecosystem line, not a button.
    assert re.search(r'class="btn[^"]*"[^>]*href="https://magicconnect', html) is None
    assert 'class="footer-ecosystem"' in footer
    moseisley_count = len(re.findall(r'href="https://moseisley\.sh/\?', html))
    assert moseisley_count > len(links)


def test_homepage_footer_has_discord_join_the_crew_cta():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    # Exactly one Discord invite in the CTA.
    assert html.count("https://discord.gg/PnQGFKWMA") == 1
    # Exact copy, aria-label, and image alt.
    assert "Join the crew →" in html
    assert 'aria-label="Join the MarkMyAss Discord community"' in html
    assert 'alt="Pirate looking through a spyglass"' in html
    assert 'class="discord-footer-cta"' in html
    # The CTA lives inside the <footer>, as the footer's content.
    footer = html.split("<footer>", 1)[1].split("</footer>", 1)[0]
    assert "https://discord.gg/PnQGFKWMA" in footer
    assert "discord-footer-cta" in footer
    # Not duplicated anywhere else on the page (single CTA).
    assert html.count('class="discord-footer-cta"') == 1


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
