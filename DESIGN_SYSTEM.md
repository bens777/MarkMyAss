# GhostMark Design System

**Brand concept:** Pirates hunting ghost marks hidden inside digital cargo.
Retro pirate voyage × spectral ghost signals × serious developer tool —
not a children's pirate game, not a flat black SaaS dashboard, not neon
cybersecurity kitsch. Developer credibility always wins over decoration.

This is the second major iteration of this system (v1 shipped a
near-black + periwinkle theme with a system-serif display font; v1 was
judged too generic/dull and fully replaced below, not patched). Researched
with the `ui-ux-pro-max` skill (`--design-system` + `--domain color`/`ux`
queries) for structural guidance (contrast minimums, motion anti-patterns,
loading-state feedback), then adapted into an original palette rather than
using any stock recommendation verbatim.

This file is the single source of truth for palette, type, spacing,
motion, and illustration rules. Page-specific deviations (if any) should
be called out explicitly in the relevant page's CSS comments, not
invented ad hoc.

## Palette: "Midnight Ocean" (dark) / "Parchment Map" (light)

All pairs below are verified against WCAG 2.1 contrast math (relative-
luminance formula, not eyeballed) using a throwaway Python script run
against the exact final hex values — never approximated by eye.

### Dark ("Midnight Ocean", default)

| Token | Hex | Role | Contrast on `--bg` |
| --- | --- | --- | --- |
| `--bg` | `#0b1d33` | Page background (midnight ocean navy, not near-black) | — |
| `--bg-void` | `#071526` | Darkest atmospheric background (hero/fog sections only) | — |
| `--surface` | `#122a48` | Card/panel background | — |
| `--surface-2` | `#1a3a5e` | Nested panel (signal rows, verdict/exiftool panels) | — |
| `--border` | `#2f5074` | Borders, dividers | — |
| `--text` | `#f5ecd8` | Primary text (warm cream/parchment, not white) | 14.4:1 (AAA) |
| `--muted` | `#aebcd1` | Secondary text | 7.9:1 (AAA) |
| `--accent` | `#e2664f` | Interactive: links, primary CTA background, active tab, hero flow | 5.1:1 as text on `--bg` |
| `--accent-ink` | `= var(--bg)` | Text color used ON an `--accent` background (buttons, active tab, skip-link) | 5.05:1 on `--accent` |
| `--brass` | `#dcac52` | Secondary accent: card top-border, dividers, tagline, small icons — nautical-instrument gold | 8.1:1 (AAA) |
| `--spectral` | `#8fe8cc` | Secondary/decorative accent: ghost glyph, focus ring, moon glow, stars — seafoam/spectral mint, never body text | 12.6:1 (AAA, though decorative use doesn't require it) |
| `--found` | `#f0ab5d` | Signal found / partial verdict | 9.7:1 (AAA) |
| `--notfound` / `--pass` | `#6fcf8e` | Signal absent / verified-clean verdict | 8.9:1 (AAA) |
| `--partial` | `#f0ab5d` | Partial verdict (= `--found`) | 9.7:1 (AAA) |
| `--danger` | `#e6543f` | Failure / destructive | 4.9:1 (AA) |
| `--unknown` | `#aebcd1` | Unknown/uncharted (= `--muted`) | 7.9:1 (AAA) |

**Rule: green is reserved for verified/success states only.** It is never
used decoratively elsewhere in the palette (the old system's spectral
cyan and this system's spectral mint both deliberately avoid reading as
"success" at a glance).

### Parchment (sparing use — decorative "manifest/log" framing only)

| Token | Hex | Role |
| --- | --- | --- |
| `--parchment` | `#f4ecd8` (dark mode) / `#ddc99a` (light mode) | Warm paper surface for an occasional "ship's log" callout (`.log-entry`) |
| `--parchment-ink` | `#22314a` | Text color used ONLY on `--parchment` (9.9:1+ AAA in both modes) |

**Why `--parchment` itself changes per mode:** in light mode the page
background is already parchment-toned (`--bg: #f4ecd8`), so a `.log-entry`
callout needs a visibly deeper "aged paper" shade plus its own border to
still read as a distinct panel — reusing the dark-mode value would make
the callout blend into the page. `--brass` is never used as text on
`--parchment` in either mode (fails contrast) — brass-on-parchment is
decorative-only (a rule, a label, an icon stroke); text on parchment
always uses `--parchment-ink` or the fixed link color `#5a4210` (dark
mode, 8.0:1) which is re-verified against the light-mode parchment shade
too (5.8:1).

### Light ("Parchment Map", `prefers-color-scheme: light`)

| Token | Hex | Contrast on `--bg` |
| --- | --- | --- |
| `--bg` | `#f4ecd8` | — |
| `--surface` | `#fbf6ea` | — |
| `--border` | `#d8c9a3` | — |
| `--text` | `#22314a` | 13.9:1 (AAA) |
| `--muted` | `#5c6b82` | 4.7:1 (AA) |
| `--accent` | `#b93b25` | 4.5:1 (AA) — deliberately darker than the dark-mode coral so it still clears AA on a light page |
| `--accent-ink` | `#ffffff` | 5.65:1 on `--accent` |
| `--brass` | `#8a641c` | 4.55:1 (AA) |
| `--spectral` | `#166b5a` | darker green-teal so it stays legible as text/strokes on a light page (the dark-mode mint would fail) |
| `--found` / `--partial` | `#8f4f0e` | 5.4:1 (AA) |
| `--notfound` / `--pass` | `#1f7a45` | 5.9:1 (AA) |
| `--danger` | `#b23223` | 5.5:1 (AA) |

## Typography

**No external font CDN at runtime** — GhostMark's privacy stance
(`PRIVACY.md`: "No CDN JavaScript or remote fonts") is a hard constraint.
The one addition below is a **self-hosted** file bundled with the app, not
a network request to Google Fonts or any other third party.

- **Display (H1, hero heading, article H1/H2, "Captain's Log"-style
  section headings, tagline):** `"Playfair Display", Georgia, "Iowan Old
  Style", "Palatino Linotype", "Book Antiqua", serif` — `--font-display`.
  `Playfair Display` bold (weight 700, Latin subset only, ~38KB woff2) is
  self-hosted at `static/fonts/playfair-display-v40-latin-700.woff2`
  under the SIL Open Font License 1.1 (license text bundled alongside it
  at `static/fonts/OFL.txt`; see `THIRD_PARTY_LICENSES.md`). `font-display:
  swap` avoids invisible text during load; the Georgia-based fallback
  stack renders immediately and is visually close enough that the swap is
  unobtrusive. This is a dramatic, editorial, slightly vintage serif —
  used for headings only, never body copy or technical output.
- **Body, controls, technical results, tables:** unchanged system font
  stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto,
  sans-serif`) — `--font-body`. Developer readability comes first; this
  remains a fast, zero-dependency choice.
- **Code, hashes, metadata values:** `ui-monospace, SFMono-Regular, "SF
  Mono", Consolas, "Liberation Mono", monospace` — `--font-mono`.
- **Never** use a novelty/pirate display face for body or UI text —
  Playfair Display is dramatic but fully legible prose type, not a
  gimmick font, and is reserved for headings.

## Spacing, radius, shadow

- Spacing: existing rem-based scale (`0.3rem`/`0.5rem`/`0.75rem`/`1rem`/
  `1.5rem`/`2rem`) — an approximate 4/8pt rhythm, kept as-is.
- Radius: `6px`–`8px` (buttons, tabs, inputs, signal rows), `10px`
  (panels), `10px` (cards, tightened slightly from the previous `12px`
  to read less "bubbly" against the new sharper brass top-border).
- Shadow: cards/panels ("manifest console" components) now use a
  deliberate `box-shadow: 0 6px 20px rgba(0,0,0,0.16)` plus a **3px solid
  `--brass` top border** — the combination is what makes a card read as a
  distinct panel/manifest rather than a flat rectangle, replacing the
  previous border-only approach now that the darker navy background gives
  a shadow room to actually show.

## Atmosphere: background texture

`body` carries two lightweight, pure-CSS `background-image` gradients (no
image request, no layout cost): a very low-opacity radial "horizon glow"
tinted with `--spectral` near the top of the page, and a faint repeating
horizontal-line texture (`color-mix(in srgb, var(--text) 3%, transparent)`)
suggesting chart-plotting lines. Both are intentionally subtle — the goal
is atmosphere, not a pattern that competes with foreground text contrast
(the contrast ratios in the Palette section are computed against the flat
`--bg` color; the texture's opacity is low enough to not measurably affect
them).

## Icons & illustration

Two deliberately different tiers, not one style stretched too thin:

1. **The homepage hero scene** (`static/art/hero-fleet.webp`) is a single
   wide, detailed, cel-shaded illustration — the one place the pirate/
   ghost world gets to be genuinely rich. A disciplined four-color
   palette (navy / brass-amber / cream / spectral mint — the same tokens
   as the rest of the site, not an arbitrary illustration palette), one
   bold graphic ghost-silhouette flag as the singular iconic emblem
   (deliberately as bold/simple as a classic skull-and-crossbones), and a
   crew whose poses tell the product's actual story: a captain in a
   confident, victorious stance with a spyglass, crew celebrating with
   raised fists, a spectral ghost visibly startled and dissolving into
   particles as it's caught escaping an inspected crate. That narrative
   ("the pirates found and defeated the hidden watermark ghost") is a
   deliberate choice, not incidental detail — the emotional beat is part
   of the brief whenever this asset is regenerated. Produced with an AI
   image-generation tool from an original text prompt (no reference
   image, no third-party/franchise input) — see `THIRD_PARTY_LICENSES.md`.
   Shipped as a single bundled `.webp` (no runtime generation, no
   external request at page-load time), ~2400px wide / ~205KB.
   **Full-bleed, not boxed:** the illustration is a `background-image` on
   `.hero-banner` spanning the entire viewport width (breaks out of
   `.wrap` via a negative-margin trick), not an `<img>` inside a
   two-column card — a boxed picture next to text reads as "generic SaaS
   with an illustration pasted on the side"; a full-bleed backdrop reads
   as an environment the page lives in. The source composition was
   deliberately prompted with an empty, uncluttered left third so the
   copy (inside `.hero-copy`) has somewhere calm to sit; a `linear-
   gradient` scrim on `.hero-banner::before` is a safety net for
   contrast, not the primary legibility mechanism. On narrow viewports,
   text is never overlaid on the image (a copy block this long doesn't
   fit any reasonable image-band height) — instead a short decorative
   image strip sits above fully-solid-background copy in normal
   document flow; see the `@media (max-width: 860px)` rule. Because it's
   a CSS background, it has zero DOM/accessibility-tree presence — no
   `alt`, no `aria-hidden`, nothing for a screen reader to skip.
   **If this asset is ever regenerated:** keep the same brief (original
   composition, no copyrighted characters/franchise/logos, the site's
   four-color palette, the victorious-pirates/defeated-ghost narrative,
   an empty left third for text) and re-optimize to a similar file size
   before committing.
2. **Everything else** stays simple, original, single-weight SVG line
   art (rects, circles, paths built from arcs/lines, ~2px stroke) —
   small supporting icons and secondary-page hero art, not attempts at
   the same painterly density as the homepage hero. No filled/outline
   mixing within one icon, no gradients, no photorealism, no copyrighted
   characters or franchise imagery.

- **Self-theming pattern (required for SVG):** every SVG under
  `static/art/` and `static/run-local-hero.svg` is referenced via `<img
  src="...">`, which does **not** inherit the host page's CSS custom
  properties or `currentColor`. Each file is therefore self-theming: an
  internal `<style>` block with hardcoded hex values (matching the
  tokens above) plus its own `@media (prefers-color-scheme: light)`
  override. Never rely on inherited page CSS for an `<img>`-referenced
  SVG. (Not applicable to the raster hero, which is pre-rendered for the
  dark palette and displayed identically in both color schemes — its own
  night-scene lighting reads fine against either page background.)
- **XML comment gotcha:** SVG/XML comments cannot contain a literal `--`
  anywhere in the body (only immediately before the closing `-->`) — a
  comment like `<!-- imagery -- simple shapes -->` is invalid XML and
  silently breaks the entire file's rendering in the browser (no error
  shown, the `<img>` just renders as empty/broken). Validate new/edited
  SVGs with `python -c "import xml.etree.ElementTree as ET; ET.parse(path)"`
  before committing.
- **SVG asset set** (`static/art/`, reused rather than one illustration
  per page):
  - `mascot-captain.svg` — a smaller captain + spyglass + ghost/document
    vignette, available for reuse in empty states or smaller contexts.
  - `spyglass.svg` — inspection motif; used on the Cleaner's Inspect
    stage heading.
  - `ghost-mark.svg` — a single spectral ghost, for "signal detected"
    moments, the Clean stage heading, and empty states.
  - `compass-rose.svg` — Lab / navigation-of-the-unknown motif.
  - `verify-seal.svg` — a wax-seal/stamp shape for the Verify stage
    heading.
  - `run-local-hero.svg` (`static/`, not `static/art/`) — a ship leaving
    a harbor, for the Run Models Locally page.
  - `wave-divider.svg` — a low-key horizontal wave motif for section
    breaks.
- **Decorative vs. meaningful:** every decorative SVG is inlined with
  `aria-hidden="true"` (or `<img alt="">` for `<img>`-referenced
  versions) so screen readers skip it entirely. None of them carry
  information that isn't also present as real text.
- **Never encode status by shape/color alone** — every themed status
  indicator sits next to the literal word (FOUND / VERIFIED CLEAN /
  PARTIAL / UNKNOWN / PASS / FAIL), never instead of it. Verdict panels
  additionally get a status-colored left border (solid for pass/partial/
  failed, **dashed** for unverified/unknown — "uncharted waters" gets its
  own line style, not just a color) as a second, non-color-only signal.

## Motion

- Duration: 150–300ms for micro-interactions (button press, ghost
  fade-in/out, verdict badge stamp), matching `ui-ux-pro-max`'s animation
  guidance. Nothing loops indefinitely near technical results.
- Easing: `ease-out` for things entering/appearing, `ease-in` for things
  leaving/dissolving.
- **`prefers-reduced-motion: reduce` disables all decorative motion**
  (ghost fade, seal stamp, hero settle-in) via a single global media
  query in `style.css`, so new animations are automatically motion-safe
  without needing their own opt-out.
- Only `transform`/`opacity` are animated (never `width`/`height`/`top`/
  `left`), so nothing here can cause layout shift.
- At most one decorative animation plays per state transition, and never
  on a loop — e.g. the verdict badge "stamps" in once when verification
  completes; the hero illustration settles in once on load.

## What this system explicitly avoids

- Decorative pirate/ghost language inside machine-readable output (JSON
  receipts, `/api/*` responses, CLI `--json`) — theming is a
  presentation-layer concern only.
- Replacing precise technical terms (FOUND / NOT FOUND / UNKNOWN /
  VERIFIED CLEAN / PARTIAL / etc.) or the real CTA labels (Inspect /
  Clean File / Verify Independently / Download Clean File) with in-theme
  language anywhere a user or a machine needs to read a real result or
  take a real action. Stage "flavor" lines (e.g. "Clear the deck") sit
  alongside the real heading/button text, never replace it.
- Turning providers (Claude, C2PA, EXIF, ...) into literal fictional map
  "islands" in the Lab — the capability matrix stays a plain, directly
  readable table generated from `lab_data.py`; the pirate-map framing
  lives in the surrounding prose and header art, not the data.
- Emoji as icons (original SVG only).
- Any new external network request (fonts, CDN scripts, tracking) — the
  self-hosted display font is the one typography addition, and it never
  contacts a third party at runtime.
