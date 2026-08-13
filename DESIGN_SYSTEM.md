# MarkMyAss Design System

**Brand concept:** a high-converting indie-software landing page first, a
pirates-vs-ghosts brand personality layered on top of it second. Pirates =
control, independence, finding and cleaning hidden signals. Ghosts =
invisible metadata, hidden Unicode, provenance traces the user can't
normally see. The product must remain the main character; the universe is
strategic seasoning, not the whole meal.

**This is a from-zero rebuild, not a patch.** The previous iteration (a
warm-parchment palette rendered with an antique serif display font,
soft-shadow cards, and a small boxed illustration) is not reused, extended,
or referenced below — every token, the typography choice, the component
shape language, and the hero illustration concept were redecided from
scratch against this brief:

- bold, fun, memorable, highly usable, internet-native, shareable, modern,
  conversion-focused, slightly rebellious, technically credible
- explicitly NOT: dark fantasy, cinematic pirate movie, children's
  cartoon, generic SaaS, corporate enterprise, flat boring template,
  stock-art landing page, old-fashioned pirate-parchment website

This file is the single source of truth for palette, type, spacing,
motion, and illustration rules going forward.

## Palette

Bright warm-cream base, deep navy ink, one punchy coral-red used
everywhere brand-colored TEXT is needed, and gold/turquoise reserved for
**decoration only** (icon fills, borders, tinted badge backgrounds) —
never as small foreground text. That split exists because gold and
turquoise at a vivid, non-muddy saturation both fail 4.5:1 against a
bright cream page; keeping them decorative lets them stay vivid instead of
getting dialed back into "readable brown" and "readable teal," which is
exactly the muddy/historical-parchment look this rebuild is moving away
from. Every pairing below was checked with the WCAG relative-luminance
formula against the exact background it actually renders on (page `--bg`,
card `--surface`, or the tinted `--surface-2` chip background), not
eyeballed.

### Light (default, unconditional — regardless of OS `prefers-color-scheme`)

| Token | Hex | Role | Contrast |
| --- | --- | --- | --- |
| `--bg` | `#fff6e7` | Page background — bright warm cream | — |
| `--bg-void` | `#fbeac9` | Deepest atmospheric background (rare) | — |
| `--surface` | `#ffffff` | Card/panel background | — |
| `--surface-2` | `#fff1dc` | Nested panel (signal rows, verdict/exiftool panels) | — |
| `--border` | `#f0ddba` | Borders, dividers | — |
| `--text` | `#12213d` | Primary text — deep navy, not black | 14.9:1 (AAA) on `--bg` |
| `--muted` | `#56638a` | Secondary text | 5.5:1 (AA) on `--bg` |
| `--accent` | `#cc2a14` | THE brand text color: links, kicker, tagline, hover states, primary CTA background | 5.0:1 on `--bg`, 4.8:1 on `--surface-2` |
| `--accent-ink` | `#ffffff` | Text on an `--accent` background | 5.4:1 on `--accent` |
| `--brass` | `#e8a233` | Decorative only — icon fills, borders, badge chips. Never text. | — |
| `--spectral` | `#12b8a6` | Decorative only — ghost/provenance icon fills, borders, tinted callouts. Never text. | — |
| `--found` / `--partial` | `#aa4b16` | Signal found / partial verdict badge text | 5.1:1 on `--surface-2` |
| `--notfound` / `--pass` | `#177843` | Signal absent / verified-clean verdict badge text | 5.0:1 on `--surface-2` |
| `--danger` | `#d4242f` | Failure / destructive | 4.6:1 on `--surface-2` |
| `--unknown` | `#56638a` | Unknown/uncharted (= `--muted`) | 5.3:1 on `--surface-2` |

**Rule: `--brass` and `--spectral` are decorative-only, never a text
color.** If a new component needs brand-colored text, use `--accent`. This
is a hard rule, not a style preference — both fail 4.5:1 against every
light-mode background at a saturation worth calling "gold" or
"turquoise."

**Rule: green is reserved for verified/success states only.**

### Parchment (sparing use — an occasional "ship's log" callout only)

| Token | Hex | Role |
| --- | --- | --- |
| `--parchment` | `#f6dfaf` (light) / `#f5dfb0` (dark) | Warm paper surface for `.log-entry` |
| `--parchment-ink` | `#12213d` | Text on `--parchment` (12.3:1 AAA) |

### Dark (opt-in, `prefers-color-scheme: dark` only — never the fallback)

| Token | Hex |
| --- | --- |
| `--bg` | `#0e1b33` |
| `--bg-void` | `#081222` |
| `--surface` | `#16294a` |
| `--surface-2` | `#1e3a63` |
| `--border` | `#2c4a72` |
| `--text` | `#fbf3e2` |
| `--muted` | `#a9bad9` |
| `--accent` | `#ff6b4a` |
| `--accent-ink` | `#0e1b33` |
| `--brass` | `#f2b84d` (decorative only) |
| `--spectral` | `#4fe0cc` (decorative only) |
| `--found` / `--partial` | `#ffb066` |
| `--notfound` / `--pass` | `#6fe0a0` |
| `--danger` | `#ff8a80` |
| `--unknown` | `#a9bad9` |

If you change either palette, keep `:root` (the unconditional default) and
the `dark` media query in sync — every token must be defined in both
places, and every self-theming SVG under `static/art/` follows the
identical pattern (see Icons & illustration below) and must be updated to
match.

## Typography

**No external font CDN at runtime** — a hard constraint (`PRIVACY.md`: "No
CDN JavaScript or remote fonts").

**One font family, everywhere, headings included:** `-apple-system,
BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif` —
`--font-body` and `--font-display` are now the same stack. A previous
iteration used a self-hosted antique serif (Playfair Display) for every
heading; it read as an old-fashioned pirate-poster/parchment-website
cliché, exactly what this rebuild is required to avoid. Personality now
comes from **weight and spacing**, not typeface: headings are
`font-weight: 900` with tight negative letter-spacing (`-0.02em`), the
brand kicker is a small bold uppercase label with wide positive
letter-spacing (`0.14em`) — both read as modern/internet-native/bold, not
antique. No display serif ships with the app anymore; the previous
`playfair-display-v40-latin-700.woff2` + `OFL.txt` files were removed.

- **Body, controls, technical results, tables, headings:** the one system
  sans stack above. Fast, zero-dependency, and legible at every weight the
  brand needs.
- **Code, hashes, metadata values:** `ui-monospace, SFMono-Regular, "SF
  Mono", Consolas, "Liberation Mono", monospace` — `--font-mono`.
- **Never** add a decorative/novelty display face back in for headings —
  if a heading needs to feel more "brand," reach for weight/tracking/color
  (`--accent`), not a second font family.

## Spacing, radius, shadow — "sticker" component language

- Spacing: existing rem-based scale (`0.3rem`/`0.5rem`/`0.75rem`/`1rem`/
  `1.5rem`/`2rem`) — unchanged, an approximate 4/8pt rhythm.
- Radius: `--radius-sm: 10px` (buttons, tabs, inputs, signal rows),
  `--radius-md: 16px` (cards, panels), `--radius-lg: 22px` (the hero
  illustration frame, the bottom promo card) — visibly rounder than the
  previous iteration's `10px` cards, for a softer/friendlier/more
  internet-native shape language.
- Shadow: cards, buttons, and preview tiles use a **flat, hard-edged
  "sticker" offset shadow** (`box-shadow: 4px 4px 0 var(--text)`, no
  blur) plus a bold `2px solid var(--text)` outline, instead of the
  previous soft `rgba` drop-shadow + colored top-border. Interactive
  elements shift toward their shadow on hover (`translate(-2px,-2px)` +
  a bigger offset) and "press into" it on click
  (`translate(2px,2px)` + a smaller offset) — a tactile, slightly
  playful, unmistakably non-corporate interaction that reads as
  confident/bold/shareable rather than soft/muted/parchment-y.

## Icons & illustration

**Hero illustration — the mandatory brand scene.** A pirate crew actively
hunting spectral ghosts aboard their ship, dense enough to read as a real
story at first glance: the captain on the quarterdeck locks a glowing
teal spyglass scan-cone (a diegetic "detection beam" that visually rhymes
with the product's own signal-detection UI) onto a shocked ghost; a
grinning crewmate mid-lunge swings a rope net at a large fleeing ghost
trailing luminous wisps; a third pirate throws open a treasure chest and
laughs as a startled ghost bursts out; two lookouts up in the rigging
point and shout at a fourth ghost slipping over the railing. Warm golden
lanterns hang from the rigging, their glow pooling against the cool teal
ghost-light for depth.

**Rendering style — this is the load-bearing rule.** Richly rendered,
painterly **cel-shaded** illustration with real depth, lighting, cast
shadows, and material texture (wood grain, rope fiber, patched
sailcloth) — the register of premium indie-game key art. It is
explicitly **not** flat corporate vector (an earlier iteration failed
exactly that way — thick-outline two-tone flat shapes read as generic
startup clip art and were rejected), not pixel art, not dark cinematic
concept art, not a children's-book cartoon, and not photoreal. Bright,
warm, optimistic overall lighting on a cream sky/sea backdrop; drama
comes from character acting and the warm-vs-teal light contrast, never
from darkness. If this asset is ever regenerated: keep the prompt free
of the words "flat", "vector", "minimal", or "geometric"; demand
texture, lighting and depth in so many words; and supply the
`design-references/` images to the generator as actual image inputs
(quality/energy references with an explicit do-not-copy-style
instruction) — describing them in prose only has empirically produced
flat-vector regressions.

Colors match the site's palette tokens (cream, navy, coral, brass gold,
turquoise). Generated with an AI image-generation tool from an original
text prompt, with the two `design-references/` screenshots supplied as
quality/energy references only (see `THIRD_PARTY_LICENSES.md` for the
originality review). Shipped as a single bundled
`static/art/hero-scene.webp` (1376×768, ~185KB, no runtime generation,
no external request at page-load time).

**Placement is deliberately restrained: the illustration supports the
product, it doesn't replace it.** The hero is a classic two-column
conversion layout: copy/CTAs/trust-bar in the left column, the
illustration *contained* in the right column at its natural aspect
ratio (rounded frame, its own sticker border+shadow) — never a
full-bleed backdrop spanning the viewport. The cleaner tool panel sits
in its own strong block immediately below the hero. On mobile
(≤900px) the hero stacks: copy first, illustration second, cleaner
after. Page structure was decided first, without the illustration: the
headline, the Inspect→Clean→Verify strip, the CTA, and the trust bar
all have to work and make the product findable within three seconds
even with the illustration hidden.

**The "MarkMyAss" visual joke is a sanctioned SECONDARY easter egg, never
the subject.** The hero scene carries it as a discovery detail: the
net-swinging pirate has a round skull-stamp mark printed on the seat of
his (fully clothed) trousers, and the crewmate at the treasure chest is
pointing at it mid-laugh. Rules that keep it working: everyone stays
fully clothed, nothing vulgar or sexual, the primary read of the image
remains "crew hunting hidden ghosts" — the gag is what a visitor notices
on the second look, not the first. The same "discovered mark" motif
exists as a small reusable icon (`static/art/mark-stamp.svg`, a round
woodcut skull seal) used sparingly on content surfaces (e.g. the
homepage "What MarkMyAss actually removes" heading). Brand hierarchy:
pirates = the MarkMyAss crew, ghosts = hidden traces, marks = what the
crew discovers and removes. Do not put the gag on every page — one
memorable signature beats a running joke that wears out.

**Everything else** stays simple, original, single-weight SVG line/flat
art (rects, circles, paths built from arcs/lines) — small supporting icons
across the Cleaner tool stages and secondary pages, recolored to the new
palette (gold/turquoise fills now use the decorative-only `--brass` /
`--spectral` values above). No filled/outline mixing within one icon, no
gradients, no photorealism, no copyrighted characters or franchise
imagery.

- **Self-theming pattern (required for SVG):** every SVG under
  `static/art/` and `static/run-local-hero.svg` is referenced via `<img
  src="...">`, which does **not** inherit the host page's CSS custom
  properties. Each file is therefore self-theming: an internal `<style>`
  block with hardcoded hex values matching the **default (light)
  palette**, plus its own `@media (prefers-color-scheme: dark)` override
  — kept in sync with the page's own CSS custom properties above. Never
  rely on inherited page CSS for an `<img>`-referenced SVG.
- **XML comment gotcha:** SVG/XML comments cannot contain a literal `--`
  anywhere in the body (only immediately before the closing `-->`) — a
  comment like `<!-- imagery -- simple shapes -->` is invalid XML and
  silently breaks the entire file's rendering in the browser (no error
  shown, the `<img>` just renders empty/broken). Validate new/edited SVGs
  with `python -c "import xml.etree.ElementTree as ET; ET.parse(path)"`
  before committing.
- **SVG asset set** (`static/art/`, reused rather than one illustration
  per page): `mascot-captain.svg` (captain + spyglass + ghost/document
  vignette), `spyglass.svg` (Inspect stage), `ghost-mark.svg` (signal
  detected / Clean stage), `compass-rose.svg` (Lab), `verify-seal.svg`
  (Verify stage), `run-local-hero.svg` (`static/`, ship leaving harbor —
  Run Models Locally page), `wave-divider.svg` (section-break motif).
- **Decorative vs. meaningful:** every purely decorative SVG/illustration
  is `aria-hidden="true"` (or `<img alt="">`). The hero scene is an
  exception — it's given real, specific `alt` text describing the pirates-
  hunting-ghosts action, since it's the brand's primary illustration and
  actually communicates something (not just texture).
- **Never encode status by shape/color alone** — every themed status
  indicator sits next to the literal word (FOUND / VERIFIED CLEAN /
  PARTIAL / UNKNOWN / PASS / FAIL), never instead of it. Verdict panels
  additionally get a status-colored left border (solid for pass/partial/
  failed, **dashed** for unverified/unknown) as a second, non-color-only
  signal.

## Motion

- Duration: 150–300ms for micro-interactions (button press, ghost
  fade-in/out, verdict badge stamp, hero settle-in). Nothing loops
  indefinitely near technical results.
- Easing: `ease-out` for things entering/appearing, `ease-in` for things
  leaving/dissolving.
- **`prefers-reduced-motion: reduce` disables all decorative motion** via
  a single global media query in `style.css`, so new animations are
  automatically motion-safe without needing their own opt-out.
- Only `transform`/`opacity` are animated (never `width`/`height`/`top`/
  `left`), so nothing here can cause layout shift.
- At most one decorative animation plays per state transition, never on a
  loop — the verdict badge "stamps" in once, the hero illustration
  settles in once on load.

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
- Building a pirate-themed website first and bolting software onto it.
  The page structure (nav → headline/CTA → cleaner → info → previews →
  footer) has to work and stay legible with every illustration hidden;
  the pirate/ghost universe is layered on afterward, strategically, not
  as the organizing principle.
- Turning every component into pirate cosplay. The brand universe shows
  up in the hero scene, the stage icons, and the in-theme flavor lines —
  not smeared across every card, label, and button.
- Emoji as icons (original SVG only).
- Any new external network request (fonts, CDN scripts, tracking).
- No installed design-recommendation skill was used to source this
  iteration's direction — palette, shape language, and hero composition
  were decided by direct visual reasoning against the brief above, not a
  generated style/palette/font-pairing suggestion.
