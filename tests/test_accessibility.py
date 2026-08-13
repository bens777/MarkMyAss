"""Accessibility regression tests for the brand/UX redesign.

Covers findings from a ui-ux-pro-max review pass: skip links, decorative
SVGs hidden from screen readers, visible focus states, and no infinite
decorative animation (which ui-ux-pro-max's own guidance flags -- "use
continuous animation for loading indicators only, not decorative
elements").
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
        public_url="https://ghostmark.moseisley.sh",
        session_ttl_seconds=720,
        rate_limit_per_minute=1000,
        max_concurrent_jobs=4,
        processing_timeout_seconds=30,
        max_upload_mb=20,
    )
    base.update(overrides)
    return WebConfig(**base)


def test_homepage_has_skip_link_targeting_main_content():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    assert 'href="#main-content"' in html
    assert 'id="main-content"' in html


def test_lab_page_has_skip_link_targeting_main_content():
    client = TestClient(create_app(_config()))
    html = client.get("/lab").text
    assert 'href="#main-content"' in html
    assert 'id="main-content"' in html


def test_decorative_svgs_are_hidden_from_screen_readers():
    client = TestClient(create_app(_config()))
    html = client.get("/").text
    # The brand-mark wordmark icon is decorative (the adjacent "GhostMark"
    # text already conveys the same information).
    for svg_tag in re.findall(r"<svg[^>]*>", html):
        if 'class="brand-mark"' in svg_tag:
            assert 'aria-hidden="true"' in svg_tag


def test_hero_scene_illustration_has_descriptive_alt_text():
    """The hero scene is the brand's primary illustration (pirates
    hunting spectral ghosts) and actually communicates something, so
    unlike a purely decorative icon it gets real, specific alt text
    instead of being hidden from screen readers."""

    client = TestClient(create_app(_config()))
    html = client.get("/").text
    match = re.search(r'<img src="static/art/hero-scene\.webp" alt="([^"]+)"', html)
    assert match is not None
    assert len(match.group(1)) > 20
    assert re.search(r'<img[^>]*class="mascot-idle"', html) is None


def test_buttons_have_visible_focus_style():
    css = (
        __import__("pathlib")
        .Path(__file__)
        .parent.parent.joinpath("src", "ghostmark", "web", "static", "style.css")
        .read_text(encoding="utf-8")
    )
    assert ".btn:focus-visible" in css
    assert "outline:" in css.split(".btn:focus-visible")[1][:100]


def test_no_infinite_decorative_animation():
    """ui-ux-pro-max review finding: continuous/infinite animation should
    only be used for loading indicators, never decorative elements. The
    hero mascot previously had an `infinite` sway; it now plays once."""

    css = (
        __import__("pathlib")
        .Path(__file__)
        .parent.parent.joinpath("src", "ghostmark", "web", "static", "style.css")
        .read_text(encoding="utf-8")
    )
    # Strip comments so this checks actual CSS rules, not prose (a comment
    # explaining *why* there's no infinite animation would otherwise
    # trip a naive substring check).
    css_without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert "infinite" not in css_without_comments


def test_reduced_motion_disables_all_animation():
    css = (
        __import__("pathlib")
        .Path(__file__)
        .parent.parent.joinpath("src", "ghostmark", "web", "static", "style.css")
        .read_text(encoding="utf-8")
    )
    assert "prefers-reduced-motion: reduce" in css
    reduced_block = css.split("prefers-reduced-motion: reduce")[1][:400]
    assert "animation-duration" in reduced_block
    assert "transition-duration" in reduced_block


def test_buttons_show_loading_feedback_during_async_operations():
    """ui-ux-pro-max: async operations must show feedback beyond a
    disabled button alone."""

    js = (
        __import__("pathlib")
        .Path(__file__)
        .parent.parent.joinpath("src", "ghostmark", "web", "static", "app.js")
        .read_text(encoding="utf-8")
    )
    assert "withLoadingLabel" in js


def test_no_horizontal_overflow_safety_net_present():
    css = (
        __import__("pathlib")
        .Path(__file__)
        .parent.parent.joinpath("src", "ghostmark", "web", "static", "style.css")
        .read_text(encoding="utf-8")
    )
    assert "overflow-x: hidden" in css
