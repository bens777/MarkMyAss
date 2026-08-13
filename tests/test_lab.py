"""AI Watermark Lab: route availability, honest capability claims, no broken links."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from ghostmark.web import lab_data
from ghostmark.web.app import create_app
from ghostmark.web.config import WebConfig

LAB_SLUGS = ["claude-watermark", "c2pa", "hidden-unicode", "pdf-metadata"]


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


def test_lab_index_route():
    client = TestClient(create_app(_config()))
    resp = client.get("/lab")
    assert resp.status_code == 200
    assert "AI Watermark Lab" in resp.text


def test_lab_sub_pages_all_exist():
    client = TestClient(create_app(_config()))
    for slug in LAB_SLUGS:
        resp = client.get(f"/lab/{slug}")
        assert resp.status_code == 200, f"/lab/{slug} did not return 200"


def test_lab_unknown_slug_404s():
    client = TestClient(create_app(_config()))
    resp = client.get("/lab/does-not-exist")
    assert resp.status_code == 404


def test_lab_index_has_no_unrendered_placeholders():
    client = TestClient(create_app(_config()))
    resp = client.get("/lab")
    assert "{{" not in resp.text
    assert "}}" not in resp.text


def test_lab_sub_pages_have_no_unrendered_placeholders():
    client = TestClient(create_app(_config()))
    for slug in LAB_SLUGS:
        resp = client.get(f"/lab/{slug}")
        assert "{{" not in resp.text, f"/lab/{slug} left a template placeholder unrendered"


def test_matrix_table_present_on_index():
    client = TestClient(create_app(_config()))
    resp = client.get("/lab")
    assert "<table>" in resp.text
    for label in ["Hidden Unicode", "PDF metadata", "C2PA", "Claude statistical text watermark"]:
        assert label in resp.text


def test_matrix_never_claims_full_yes_for_c2pa_or_statistical():
    """USE ACTUAL CAPABILITIES -- these must never read as a flat "Yes"."""

    c2pa = lab_data.signal_by_key("c2pa")
    assert c2pa.detect != "Yes"
    assert c2pa.remove != "Yes"
    for key in ("claude_statistical_watermark", "gemini_statistical_watermark", "gpt_statistical_watermark"):
        signal = lab_data.signal_by_key(key)
        assert signal.detect == "Unknown"
        assert signal.remove == "Unknown"


def test_claude_page_distinguishes_the_three_mechanisms():
    client = TestClient(create_app(_config()))
    resp = client.get("/lab/claude-watermark")
    text = resp.text
    assert "File / metadata provenance" in text or "metadata provenance" in text
    assert "Hidden Unicode" in text
    assert "Statistical" in text or "statistical" in text
    # The core honesty rule from the product spec: never call hidden
    # Unicode "the Claude statistical watermark".
    assert "hidden Unicode characters in text</strong> a" not in text or "not correct" in text.lower()
    assert "This is not correct" in text or "is not a statistical signature" in text


def test_claude_page_never_conflates_hidden_unicode_with_the_watermark():
    client = TestClient(create_app(_config()))
    text = client.get("/lab/claude-watermark").text
    lowered = text.lower()
    # The literal phrase this page must never assert as fact.
    assert "hidden unicode is the claude statistical watermark" not in lowered
    assert "hidden unicode is a claude watermark" not in lowered


def test_claude_page_reports_unknown_not_fabricated():
    client = TestClient(create_app(_config()))
    text = client.get("/lab/claude-watermark").text
    assert "Unknown" in text
    assert "UNKNOWN" in text or "NOT CURRENTLY VERIFIABLE" in text


def test_c2pa_page_distinguishes_from_cryptographic_validation():
    client = TestClient(create_app(_config()))
    text = client.get("/lab/c2pa").text
    assert "cryptographic" in text.lower()
    assert "not a claim" in text.lower() or "not perform" in text.lower() or "not audited" in text.lower()


def test_every_lab_page_has_correction_cta_and_last_reviewed():
    client = TestClient(create_app(_config()))
    for slug in ["", *LAB_SLUGS]:
        path = "/lab" if slug == "" else f"/lab/{slug}"
        text = client.get(path).text
        assert "github.com/bens777/ghostmark/issues" in text, f"{path} missing issues link"
        assert "Last reviewed" in text, f"{path} missing Last reviewed date"


def test_every_lab_page_has_at_least_one_official_source_link():
    client = TestClient(create_app(_config()))
    expected_domain_per_slug = {
        "claude-watermark": "support.claude.com",
        "c2pa": "c2pa.org",
        "hidden-unicode": "unicode.org",
        "pdf-metadata": "iso.org",
    }
    for slug, domain in expected_domain_per_slug.items():
        text = client.get(f"/lab/{slug}").text
        assert domain in text, f"/lab/{slug} missing expected source domain {domain}"


def test_no_root_absolute_links_on_lab_pages():
    """Every internal link must be relative (resolves against <base href>),
    never root-absolute -- otherwise it breaks under the /ghostmark/ subpath."""

    client = TestClient(create_app(_config()))
    for slug in ["", *LAB_SLUGS]:
        path = "/lab" if slug == "" else f"/lab/{slug}"
        html = client.get(path).text
        html_without_base = re.sub(r"<base[^>]*>", "", html)
        for match in re.finditer(r'(?:href|src)="([^"]*)"', html_without_base):
            value = match.group(1)
            if value.startswith(("http://", "https://", "#", "mailto:")):
                continue
            assert not value.startswith("/"), f"{path}: root-absolute link {value!r} will bypass /ghostmark/"


def test_lab_sibling_links_include_lab_prefix():
    """Regression guard for the base-href gotcha: a link from /lab/index.md
    to a sibling page must be written as "lab/<slug>", not just "<slug>" --
    otherwise it resolves to the site root instead of under /lab/."""

    client = TestClient(create_app(_config()))
    html = client.get("/lab").text
    for slug in ["hidden-unicode", "pdf-metadata", "c2pa", "claude-watermark"]:
        assert f'href="lab/{slug}"' in html, f"expected a lab/{slug}-prefixed link on the Lab index"


def test_api_lab_status_endpoint():
    client = TestClient(create_app(_config()))
    resp = client.get("/api/lab/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "ghostmark_version" in body
    assert "tested_at" in body
    assert isinstance(body["signals"], list)
    assert len(body["signals"]) == len(lab_data.LAB_SIGNALS)
    keys = {s["key"] for s in body["signals"]}
    assert "hidden_unicode" in keys
    assert "c2pa" in keys
    assert "claude_statistical_watermark" in keys


def test_api_lab_status_never_claims_yes_for_statistical_watermarks():
    client = TestClient(create_app(_config()))
    body = client.get("/api/lab/status").json()
    for signal in body["signals"]:
        if "statistical" in signal["key"]:
            assert signal["detect"] == "Unknown"
            assert signal["remove"] == "Unknown"


def test_api_lab_status_leaks_no_filesystem_paths():
    client = TestClient(create_app(_config()))
    text = client.get("/api/lab/status").text
    assert "C:\\" not in text
    assert "/home/" not in text
    assert "src/ghostmark" not in text


def test_home_page_links_to_lab():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'href="lab"' in html
