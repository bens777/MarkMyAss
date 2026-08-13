"""Automated indexability + structured-data checks across every public page.

Covers section 19 of the SEO build spec: every indexable page returns
200, has a title/description/canonical/H1, isn't accidentally noindexed,
robots.txt/sitemap.xml are correct and don't leak internal routes,
structured data parses as valid JSON and never fabricates ratings, and
landing pages are genuinely distinct (a lightweight anti-doorway-page
guard), not the same content with a keyword swapped in.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from ghostmark.web.app import INDEXABLE_PAGES, create_app
from ghostmark.web.config import WebConfig

PUBLIC_URL = "https://ghostmark.moseisley.sh"


def _config(**overrides) -> WebConfig:
    base = dict(
        mode="hosted",
        base_path="/",
        public_url=PUBLIC_URL,
        session_ttl_seconds=720,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=20,
    )
    base.update(overrides)
    return WebConfig(**base)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(_config()))


LANDING_PAGE_PATHS = [
    p
    for p in INDEXABLE_PAGES
    if p not in ("/", "/lab", "/benchmarks", "/run-ai-locally")
]


# --- Per-page indexability -------------------------------------------------------------


@pytest.mark.parametrize("path", INDEXABLE_PAGES)
def test_page_returns_200(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} returned {resp.status_code}"


@pytest.mark.parametrize("path", INDEXABLE_PAGES)
def test_page_has_title_and_description(client, path):
    html = client.get(path).text
    title_match = re.search(r"<title>(.*?)</title>", html, re.S)
    assert title_match and title_match.group(1).strip(), f"{path} missing/empty <title>"
    desc_match = re.search(r'<meta name="description" content="(.*?)"', html)
    assert desc_match and desc_match.group(1).strip(), f"{path} missing/empty meta description"


@pytest.mark.parametrize("path", INDEXABLE_PAGES)
def test_page_has_correct_canonical(client, path):
    html = client.get(path).text
    match = re.search(r'rel="canonical" href="(.*?)"', html)
    assert match, f"{path} missing canonical link"
    expected = PUBLIC_URL if path == "/" else PUBLIC_URL + path
    assert match.group(1) == expected, f"{path} canonical {match.group(1)!r} != {expected!r}"


@pytest.mark.parametrize("path", INDEXABLE_PAGES)
def test_page_has_exactly_one_h1(client, path):
    html = client.get(path).text
    h1s = re.findall(r"<h1[ >]", html)
    assert len(h1s) == 1, f"{path} has {len(h1s)} <h1> elements, expected exactly 1"


@pytest.mark.parametrize("path", INDEXABLE_PAGES)
def test_page_is_not_accidentally_noindexed(client, path):
    html = client.get(path).text
    assert "noindex" not in html.lower()
    robots_match = re.search(r'<meta name="robots" content="(.*?)"', html)
    if robots_match:
        assert "index" in robots_match.group(1) and "noindex" not in robots_match.group(1)


@pytest.mark.parametrize("path", INDEXABLE_PAGES)
def test_page_has_no_root_absolute_internal_links(client, path):
    """Every internal link must be base-href-relative (no leading '/'),
    matching the reverse-proxy subpath convention used across the site."""

    html = client.get(path).text
    html_without_base = re.sub(r"<base[^>]*>", "", html)
    for attr in ("href", "src"):
        for match in re.finditer(rf'{attr}="([^"]*)"', html_without_base):
            value = match.group(1)
            if value.startswith(("http://", "https://", "#", "mailto:")):
                continue
            assert not value.startswith("/"), f"{path}: {attr}=\"{value}\" is root-absolute"


# --- robots.txt / sitemap.xml -----------------------------------------------------------


def test_robots_txt_allows_root_and_disallows_api(client):
    text = client.get("/robots.txt").text
    assert "User-agent: *" in text
    assert "Allow: /" in text
    assert "Disallow: /api/" in text
    assert f"Sitemap: {PUBLIC_URL}/sitemap.xml" in text


def test_robots_txt_never_mentions_session_or_download_paths(client):
    text = client.get("/robots.txt").text
    assert "session" not in text.lower()
    assert "download" not in text.lower()


def test_sitemap_is_valid_xml(client):
    text = client.get("/sitemap.xml").text
    root = ET.fromstring(text)  # raises if malformed
    assert root.tag.endswith("urlset")


def test_sitemap_contains_every_indexable_page_as_absolute_canonical_url(client):
    text = client.get("/sitemap.xml").text
    for path in INDEXABLE_PAGES:
        expected = PUBLIC_URL if path == "/" else PUBLIC_URL + path
        assert f"<loc>{expected}</loc>" in text, f"sitemap missing {expected}"


def test_sitemap_never_lists_api_or_session_routes(client):
    text = client.get("/sitemap.xml").text
    assert "/api/" not in text
    assert "download" not in text.lower()
    assert "receipt" not in text.lower()


def test_sitemap_content_type_is_xml(client):
    resp = client.get("/sitemap.xml")
    assert "xml" in resp.headers["content-type"]


# --- Structured data ---------------------------------------------------------------------


def _jsonld_blocks(html: str) -> list[dict]:
    blocks = []
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        data = json.loads(match.group(1))  # raises if malformed
        blocks.extend(data if isinstance(data, list) else [data])
    return blocks


def test_homepage_has_software_application_and_website_jsonld(client):
    blocks = _jsonld_blocks(client.get("/").text)
    types = {b.get("@type") for b in blocks}
    assert "SoftwareApplication" in types
    assert "WebSite" in types


def test_software_application_jsonld_never_fabricates_ratings_or_reviews(client):
    blocks = _jsonld_blocks(client.get("/").text)
    app_block = next(b for b in blocks if b.get("@type") == "SoftwareApplication")
    assert "aggregateRating" not in app_block
    assert "review" not in app_block
    assert app_block["offers"]["price"] == "0"


@pytest.mark.parametrize("path", LANDING_PAGE_PATHS)
def test_landing_pages_have_breadcrumb_jsonld(client, path):
    blocks = _jsonld_blocks(client.get(path).text)
    breadcrumb = next((b for b in blocks if b.get("@type") == "BreadcrumbList"), None)
    assert breadcrumb is not None, f"{path} missing BreadcrumbList structured data"
    items = breadcrumb["itemListElement"]
    assert items[0]["name"] == "Home"
    assert items[0]["item"] == PUBLIC_URL
    assert items[-1]["item"] == PUBLIC_URL + path


def test_no_faqpage_jsonld_anywhere(client):
    """Google removed FAQ rich results from Search in 2026 -- implementing
    FAQPage markup here would be dead weight, see seo.py's module docstring."""

    for path in INDEXABLE_PAGES:
        blocks = _jsonld_blocks(client.get(path).text)
        assert not any(b.get("@type") == "FAQPage" for b in blocks), f"{path} has unnecessary FAQPage markup"


# --- Anti-doorway-page guard ---------------------------------------------------------------


def _article_word_set(html: str) -> set[str]:
    body = re.search(r"<article[^>]*>(.*?)</article>", html, re.S)
    text = re.sub(r"<[^>]+>", " ", body.group(1)) if body else ""
    words = re.findall(r"[a-z]{4,}", text.lower())
    return set(words)


def test_landing_pages_are_not_near_duplicates_of_each_other(client):
    """Lightweight anti-doorway-page guard: no two landing pages should be
    the same content with a keyword swapped in (Jaccard similarity of
    their body word sets should stay well below "basically identical")."""

    word_sets = {path: _article_word_set(client.get(path).text) for path in LANDING_PAGE_PATHS}
    paths = list(word_sets)
    for i, path_a in enumerate(paths):
        for path_b in paths[i + 1 :]:
            a, b = word_sets[path_a], word_sets[path_b]
            jaccard = len(a & b) / len(a | b)
            assert jaccard < 0.6, f"{path_a} and {path_b} are {jaccard:.0%} similar -- looks like a doorway page pair"


def test_each_landing_page_has_a_distinct_title(client):
    titles = set()
    for path in LANDING_PAGE_PATHS:
        html = client.get(path).text
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        assert title not in titles, f"duplicate title for {path}: {title!r}"
        titles.add(title)


# --- OG image --------------------------------------------------------------------------


def test_og_image_is_served(client):
    resp = client.get("/static/og-image.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_homepage_references_og_image(client):
    html = client.get("/").text
    assert 'property="og:image"' in html
    assert 'name="twitter:image"' in html
