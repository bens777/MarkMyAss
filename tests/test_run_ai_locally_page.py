"""The /run-ai-locally developer guide: route availability, rendering, redirect, content integrity."""

from __future__ import annotations

import re

import pytest
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


@pytest.fixture()
def client():
    return TestClient(create_app(_config()))


def test_route_is_available(client):
    resp = client.get("/run-ai-locally")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_old_url_redirects_permanently(client):
    resp = client.get("/run-local", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/ghostmark/run-ai-locally"


def test_old_url_redirects_to_working_page():
    # Uses a root base_path client: the /ghostmark/-prefixed Location header
    # is only resolvable behind a real reverse proxy that strips that
    # prefix (see deploy/Caddyfile.snippet's handle_path) -- TestClient has
    # no such proxy in front of it, so following that redirect directly
    # would 404 against the bare FastAPI route. Root base_path has no
    # prefix to strip, so the redirect is directly followable here.
    client = TestClient(create_app(_config(mode="local", base_path="/")))
    resp = client.get("/run-local", follow_redirects=True)
    assert resp.status_code == 200
    assert "Run AI Models Locally" in resp.text or "Run Models Locally" in resp.text


def test_redirect_respects_root_base_path():
    client = TestClient(create_app(_config(mode="local", base_path="/")))
    resp = client.get("/run-local", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/run-ai-locally"


def test_page_is_english_and_well_formed_html(client):
    html = client.get("/run-ai-locally").text
    assert '<html lang="en">' in html
    assert "<title>" in html and "</title>" in html
    # No leftover unconverted Markdown syntax in the rendered body.
    assert "**" not in html
    assert not re.search(r"^\|.*\|$", html, re.MULTILINE)  # raw pipe-table row


def test_seo_metadata_present(client):
    html = client.get("/run-ai-locally").text
    assert "Run AI Models Locally" in html
    assert '<meta name="description"' in html
    assert 'rel="canonical"' in html
    assert 'property="og:title"' in html
    assert 'property="og:url"' in html
    assert "https://moseisley.sh/ghostmark/run-ai-locally" in html  # canonical resolves under base_path


def test_key_sections_present(client):
    html = client.get("/run-ai-locally").text
    for heading in [
        "Hosted vs. local",
        "Decision matrix",
        "Recommendations by hardware and budget",
        "Recommended models",
        "Tools, runtimes, and installation paths",
        "Renting GPUs instead of buying",
        "Suggested paths by user type",
        "What this page does not claim",
    ]:
        assert heading in html, f"missing expected section: {heading!r}"


def test_distinguishes_closed_hosted_from_open_weight_local(client):
    html = client.get("/run-ai-locally").text
    assert "Anthropic" in html and "OpenAI" in html and "Google" in html
    assert "open-weight" in html.lower()
    assert "not published as downloadable weights" in html or "not available to run locally" in html


def test_gpu_rental_section_present_and_realistic(client):
    html = client.get("/run-ai-locally").text
    assert "Renting GPUs instead of buying" in html
    for provider_link in ["runpod.io", "lambda.ai", "vast.ai"]:
        assert provider_link in html
    # Must not freeze a specific dollar price as a hard fact.
    assert "check each provider's own pricing page" in html


def test_update_correction_cta_present(client):
    html = client.get("/run-ai-locally").text
    assert "github.com/bens777/ghostmark/issues" in html
    assert "Last reviewed" in html


def test_at_least_one_official_external_link_per_major_category(client):
    html = client.get("/run-ai-locally").text
    official_links = [
        "https://ollama.com",
        "https://github.com/ggml-org/llama.cpp",
        "https://github.com/vllm-project/vllm",
        "https://lmstudio.ai",
        "https://github.com/QwenLM",
        "https://github.com/deepseek-ai",
    ]
    for link in official_links:
        assert link in html, f"missing official link: {link}"


def test_internal_navigation_not_broken(client):
    html = client.get("/run-ai-locally").text
    # Back-to-cleaner links resolve against <base href="/ghostmark/">, i.e. "."
    assert 'href="."' in html
    assert '<base href="/ghostmark/">' in html
    # The nav brand link and the in-body back link both point at the cleaner root.
    assert html.count('href="."') >= 2


def test_home_page_links_to_run_ai_locally(client):
    html = client.get("/").text
    assert 'href="run-ai-locally"' in html
    assert "run models locally" in html.lower()


def test_static_assets_referenced_are_served(client):
    html = client.get("/run-ai-locally").text
    assert client.get("/static/article.css").status_code == 200
    assert client.get("/static/art/page-run-local.webp").status_code == 200
    assert "static/article.css" in html
    assert "static/art/page-run-local.webp" in html


def test_route_works_at_root_base_path_too():
    client = TestClient(create_app(_config(mode="local", base_path="/")))
    resp = client.get("/run-ai-locally")
    assert resp.status_code == 200
    assert '<base href="/">' in resp.text
