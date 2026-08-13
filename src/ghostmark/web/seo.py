"""JSON-LD structured data for GhostMark's public pages.

Only implements schema.org types that are actually live, supported rich
result types in Google Search as of this writing, and only with fields
GhostMark can back up:

  - ``SoftwareApplication`` -- valid without ``aggregateRating``/``review``
    (Google's rich-result eligibility requires one of those, but omitting
    them just means no rich result, not invalid markup). GhostMark has no
    real review corpus, so it never fabricates one -- see CONTRIBUTING.md
    and the project's general "no invented numbers" rule.
  - ``WebSite`` -- name + url only. No ``SearchAction``/sitelinks
    searchbox markup: Google discontinued that feature (Nov 2024) and it
    would be dead weight.
  - ``BreadcrumbList`` -- for pages one or more levels below the homepage.

Deliberately NOT implemented: ``FAQPage``. Google removed FAQ rich
results from Search entirely in 2026 (not just restricted them to
government/health sites as in the 2023 policy) -- implementing the
markup would have zero SEO effect, so it isn't worth the maintenance
surface. FAQ-style content on GhostMark's pages is still useful to
readers; it's just plain HTML, not JSON-LD.
"""

from __future__ import annotations

import json
from typing import Any

SITE_NAME = "MarkMyAss"
GITHUB_URL = "https://github.com/bens777/ghostmark"
MOSEISLEY_URL = "https://moseisley.sh"

_APPLICATION_DESCRIPTION = (
    "Free, open-source tool to inspect, remove, and independently verify "
    "supported AI metadata, hidden Unicode, and C2PA provenance signals "
    "in text, PDFs, and images."
)


def software_application_jsonld(public_url: str) -> dict[str, Any]:
    """SoftwareApplication structured data. No aggregateRating/review --
    GhostMark has no real review corpus and will not invent one."""

    base = public_url.rstrip("/")
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": SITE_NAME,
        "url": base,
        "description": _APPLICATION_DESCRIPTION,
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Web, Windows, macOS, Linux",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "USD",
        },
        "author": {
            "@type": "Organization",
            "name": "Moseisley",
            "url": MOSEISLEY_URL,
        },
        "license": f"{GITHUB_URL}/blob/main/LICENSE",
        "sameAs": [GITHUB_URL],
    }


def website_jsonld(public_url: str) -> dict[str, Any]:
    base = public_url.rstrip("/")
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": base,
    }


def breadcrumb_jsonld(public_url: str, items: list[tuple[str, str]]) -> dict[str, Any]:
    """``items`` is an ordered list of ``(name, path)`` pairs starting with
    ("Home", "/"). ``path`` is appended to ``public_url`` to form each
    breadcrumb's absolute URL."""

    base = public_url.rstrip("/")
    element_list = []
    for index, (name, path) in enumerate(items, start=1):
        url = base if path in ("", "/") else base + "/" + path.strip("/")
        element_list.append(
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": url,
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": element_list,
    }


def jsonld_script_tag(data: dict[str, Any] | list[dict[str, Any]]) -> str:
    """Render one or more JSON-LD objects as a single ``<script>`` tag.

    Escapes ``<`` so a value containing ``</script>`` can never break out
    of the tag -- standard technique for embedding JSON inside HTML.
    """

    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    safe = raw.replace("<", "\\u003c")
    return f'<script type="application/ld+json">{safe}</script>'


def breadcrumb_nav_html(public_url: str, items: list[tuple[str, str]]) -> str:
    """Visible, crawlable breadcrumb trail matching ``breadcrumb_jsonld``.

    Links use base-href-relative paths (no leading slash) like every other
    internal link in GhostMark, per the site's reverse-proxy subpath
    convention -- see content_render.py / lab_data.py for the same rule.
    """

    parts = []
    for index, (name, path) in enumerate(items):
        is_last = index == len(items) - 1
        href = "." if path in ("", "/") else path.strip("/")
        if is_last:
            parts.append(f'<span aria-current="page">{name}</span>')
        else:
            parts.append(f'<a href="{href}">{name}</a>')
    trail = ' <span class="crumb-sep">/</span> '.join(parts)
    return f'<nav class="breadcrumbs" aria-label="Breadcrumb">{trail}</nav>'
