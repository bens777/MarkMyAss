# SEO Launch Checklist

Plain-language steps for Benoit to take in Google Search Console once
`https://markmyass.com` is live. None of this guarantees search
rankings -- Google decides what to rank based on its own evaluation of
the content, competition, and relevance over time. This checklist just
makes sure Google can actually find, crawl, and understand the site;
whether it ranks well is a separate, ongoing question that depends on
things outside this checklist's control (content quality over time,
backlinks, how competitors' pages evolve, etc.).

## 0. Repository description and topics (GitHub)

This agent has no GitHub write access (no `gh` auth / API token in this
environment), so this one is manual. On the repo page
(`github.com/bens777/MarkMyAss`), click the gear icon next to **About**
and set:

- **Description**: "Open-source AI watermark & provenance cleaner.
  Inspect, clean and independently verify supported Claude, C2PA,
  metadata and hidden Unicode signals."
- **Website**: `https://markmyass.com`
- **Topics**: `ai-watermark`, `watermark-remover`, `claude`, `c2pa`,
  `content-credentials`, `metadata`, `metadata-cleaner`, `privacy`,
  `exiftool`, `provenance`, `open-source`. Keep it to topics that
  genuinely describe the project -- padding this list with unrelated
  trending tags doesn't help discoverability and looks spammy to anyone
  browsing GitHub topic pages.

## 1. Add the property

1. Go to [Google Search Console](https://search.google.com/search-console).
2. Click **Add property**.
3. Choose **Domain** property if you can (covers `markmyass.com`
   and any subpaths/protocols together) -- this requires adding a DNS TXT
   record. If that's not convenient, use a **URL prefix** property for
   `https://markmyass.com` instead; it's less complete (HTTP vs
   HTTPS and www vs non-www are tracked separately) but faster to verify.

## 2. Verify ownership

Pick whichever is easiest given how DNS/hosting is set up:

- **DNS TXT record** (required for Domain properties, works for URL
  prefix too): Search Console gives you a TXT record value to add at
  your DNS provider for `moseisley.sh`. This can take a few minutes to
  a few hours to propagate.
- **HTML file upload**: Search Console gives you a file to upload to the
  site's root. Since GhostMark's static files are served from
  `src/ghostmark/web/static/`, this would need a small route added to
  serve that file, or a file dropped into the static directory --
  simplest if using the DNS method instead.
- **HTML meta tag**: Search Console gives you a `<meta>` tag to add to
  the homepage's `<head>`. If you go this route, add it to
  `src/ghostmark/web/static/index.html` alongside the other meta tags.

DNS TXT is the recommended path here since it also covers the domain
property option and doesn't require a code change.

## 3. Submit the sitemap

1. In Search Console, go to **Sitemaps** (left sidebar, under Indexing).
2. Enter `sitemap.xml` (Search Console will resolve it against the
   verified property's domain).
3. Submit. You can check it resolves correctly first by visiting
   `https://markmyass.com/sitemap.xml` directly in a browser.

## 4. Inspect the homepage

1. Go to **URL Inspection** (top search bar in Search Console).
2. Enter `https://markmyass.com/`.
3. Confirm it shows as **not indexed yet** (expected for a new site) and
   that the "Coverage" details don't show a `noindex` or robots-blocked
   issue. If something looks wrong (blocked by robots.txt, canonical
   pointing somewhere unexpected), that's worth investigating before
   requesting indexing.

## 5. Request indexing

Still in the URL Inspection tool for the homepage, click **Request
indexing**. This asks Google to crawl the page sooner than it might
otherwise get to it -- it does not guarantee immediate indexing or any
particular ranking.

## 6. Inspect the major landing pages

Repeat the URL Inspection + Request Indexing steps (5-10 minutes total)
for the pages most likely to matter for search traffic:

- `https://markmyass.com/claude-watermark-remover`
- `https://markmyass.com/claude-watermark-detector`
- `https://markmyass.com/ai-watermark-remover`
- `https://markmyass.com/ai-metadata-cleaner`
- `https://markmyass.com/c2pa-remover`
- `https://markmyass.com/content-credentials-remover`
- `https://markmyass.com/hidden-unicode-remover`
- `https://markmyass.com/lab`

Google typically won't want every single URL manually submitted this
way (nor is that necessary once the sitemap and internal links are in
place) -- this is just to give the initial launch a nudge.

## 7. Monitor over time

Not a one-time task -- check back periodically (weekly-ish is
reasonable early on, less often later):

- **Indexing → Pages** report: shows which submitted URLs are actually
  indexed vs. excluded, and why (crawled but not indexed, discovered but
  not crawled, etc.). If a page you expect to be indexed shows as
  excluded, the reason given is usually the fastest way to diagnose it.
- **Performance** report: real search queries, impressions, clicks, and
  average position. This is where you'll actually see whether "claude
  watermark remover"-style queries are surfacing the site at all --
  there's no guarantee they will, especially early on against a crowded
  SERP (see `/lab` and the landing pages' own competitive-honesty
  framing for why GhostMark leans on accuracy rather than trying to
  out-market more aggressive competitors).
- **Core Web Vitals** (under Experience): worth a periodic glance, but
  GhostMark's frontend is deliberately minimal (no large JS frameworks,
  no external fonts/CDN scripts), so this shouldn't need much attention
  unless something regresses.

## Not covered here

- Backlink building, social promotion, or any off-site SEO -- outside
  this checklist's scope.
- Bing Webmaster Tools / other search engines -- optional, similar
  process, not covered here.
- Structured data testing: Search Console's **Enhancements** reports
  (or the standalone [Rich Results Test](https://search.google.com/test/rich-results))
  will show if the `SoftwareApplication`/`WebSite`/`BreadcrumbList`
  JSON-LD is being read correctly, once Google has crawled a page.
