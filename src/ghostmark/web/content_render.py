"""Renders long-form Markdown content pages (e.g. /run-local) into full HTML pages.

Keeps content (a plain Markdown file, easy for a future contributor to
edit without touching Python) separate from rendering logic and from the
app's own vanilla-JS single-page cleaner UI. Page metadata (title,
description, canonical path) is passed in by the route rather than
parsed out of the Markdown file, since there's currently exactly one
page and a bespoke frontmatter parser would be more machinery than the
problem needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import markdown as _markdown

from ghostmark.web.seo import breadcrumb_jsonld, breadcrumb_nav_html, jsonld_script_tag

CONTENT_DIR = Path(__file__).parent / "content"

_MARKDOWN_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "toc"]
_MARKDOWN_EXTENSION_CONFIG = {"toc": {"permalink": "#", "baselevel": 1}}


@dataclass(frozen=True)
class PageMeta:
    title: str
    description: str
    path: str  # e.g. "/run-local" -- appended to the deployment's public_url for canonical/OG
    # Ordered (name, path) pairs for BreadcrumbList + the visible breadcrumb
    # trail, starting with ("Home", "/"). None on pages that don't need one
    # (e.g. the homepage itself).
    breadcrumbs: tuple[tuple[str, str], ...] | None = None


def render_markdown_to_html(markdown_text: str) -> str:
    return _markdown.markdown(
        markdown_text,
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs=_MARKDOWN_EXTENSION_CONFIG,
        output_format="html5",
    )


def inject_context(markdown_text: str, context: dict[str, str]) -> str:
    """Substitute ``{{KEY}}`` placeholders in a Markdown source with generated content.

    Deliberately simple string substitution, not a templating engine --
    used to splice generated content (e.g. the Lab's capability table,
    itself generated from ``ghostmark.web.lab_data`` so it can never say
    something the code doesn't back up) into otherwise-static, hand-edited
    Markdown prose.
    """

    for key, value in context.items():
        markdown_text = markdown_text.replace("{{" + key + "}}", value)
    return markdown_text


def render_article_page(
    *,
    meta: PageMeta,
    body_html: str,
    base_path: str,
    public_url: str,
    nav_html: str,
    structured_data: list[dict] | None = None,
    footer_html: str | None = None,
) -> str:
    """Wrap rendered article HTML in a full page shell matching GhostMark's site chrome."""

    canonical_url = public_url.rstrip("/") + meta.path

    jsonld_blocks = list(structured_data or [])
    breadcrumb_html = ""
    if meta.breadcrumbs:
        jsonld_blocks.append(breadcrumb_jsonld(public_url, list(meta.breadcrumbs)))
        breadcrumb_html = breadcrumb_nav_html(public_url, list(meta.breadcrumbs))

    jsonld_html = "\n  ".join(jsonld_script_tag(block) for block in jsonld_blocks)

    footer = footer_html if footer_html is not None else (
        '<p>GhostMark is open source (MIT). '
        '<a href="https://github.com/bens777/ghostmark" rel="noopener">Source on GitHub</a>.</p>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <base href="{base_path}">
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{meta.title}</title>
  <meta name="description" content="{meta.description}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{canonical_url}" />

  <meta property="og:type" content="article" />
  <meta property="og:title" content="{meta.title}" />
  <meta property="og:description" content="{meta.description}" />
  <meta property="og:url" content="{canonical_url}" />
  <meta property="og:site_name" content="GhostMark" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{meta.title}" />
  <meta name="twitter:description" content="{meta.description}" />

  <link rel="stylesheet" href="static/style.css" />
  <link rel="stylesheet" href="static/article.css" />
  {jsonld_html}
</head>
<body>
  <a href="#main-content" class="skip-link">Skip to main content</a>
  <main class="wrap article-wrap" id="main-content">
    {nav_html}
    {breadcrumb_html}
    <article class="article">
{body_html}
    </article>
    <footer>
      {footer}
    </footer>
  </main>
</body>
</html>
"""
