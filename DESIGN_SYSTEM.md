# GhostMark Design System

**Brand concept:** Pirates hunting ghost marks hidden inside digital cargo.
Old pirate exploration × spectral ghosts × modern developer tooling — not
a children's pirate game, not neon cybersecurity kitsch. Developer
credibility always wins over decoration.

Researched with the `ui-ux-pro-max` skill (`--design-system` +
`--domain color`/`ux` searches against "dark developer tool", "premium
dark + gold accent", and "reduced motion / accessibility" queries), then
adapted to GhostMark's existing, already-shipped dark palette rather than
replaced wholesale — see "Why not a clean-slate palette" below.

This file is the single source of truth for palette, type, spacing,
motion, and illustration rules. Page-specific deviations (if any) should
be called out explicitly in the relevant page's CSS comments, not
invented ad hoc.

## Why not a clean-slate palette

GhostMark's existing dark theme (`--bg: #0f1115`, `--accent: #7c8cff`,
status colors) was already accessibility-tested and is referenced by
existing tests and the light-mode variant. The brand work below **extends**
it with two new semantic roles (brass, spectral) rather than discarding
what's proven. Functional status colors (found/pass/partial/danger) are
intentionally left alone — they carry meaning tested elsewhere in the
app and changing them for brand reasons alone would be decoration for
its own sake.

## Palette

All pairs below are verified against WCAG 2.1 contrast math (script used:
relative-luminance formula, not eyeballed).

### Dark (default)

| Token | Hex | Role | Contrast on `--bg` |
| --- | --- | --- | --- |
| `--bg` | `#0f1115` | Page background ("the deep") | — |
| `--bg-void` | `#0a0b0f` | Darkest atmospheric background (hero/fog sections only) | — |
| `--surface` | `#171a21` | Card/panel background | — |
| `--surface-2` | `#1d212b` | Nested panel (e.g. inside a card) | — |
| `--border` | `#2a2e38` | Borders, dividers | — |
| `--text` | `#e7e9ee` | Primary text | 15.7:1 (AAA) |
| `--muted` | `#9aa1ad` | Secondary text | 7.2:1 (AAA) |
| `--accent` | `#7c8cff` | Interactive (links, primary buttons, active states) — unchanged from the existing site | 6.4:1 (AA) |
| `--brass` | `#c9a44c` | Secondary accent: dividers, small icons, "verified/charted" motif, quotes — nautical-instrument gold | 8.1:1 (AAA) |
| `--spectral` | `#b9f5ff` | Decorative-only ghost glow (SVG strokes, subtle text-shadow) — never used for body text | 15.9:1 (AAA, though decorative use doesn't require it) |
| `--found` | `#ffb454` | Signal found (existing, unchanged) | 10.8:1 (AAA) |
| `--notfound` / `--pass` | `#5fd08a` | Signal absent / verified pass (existing, unchanged) | 9.9:1 (AAA) |
| `--partial` | `#ffb454` | Partial verdict (existing, unchanged) | 10.8:1 (AAA) |
| `--danger` | `#ff6b6b` | Failure / destructive (existing, unchanged) | 6.9:1 (AA) |
| `--unknown` | `#9aa1ad` | Unknown/uncharted (= `--muted`, existing) | 7.2:1 (AAA) |

### Parchment (sparing use — decorative "manifest" framing only)

| Token | Hex | Role |
| --- | --- | --- |
| `--parchment` | `#efe6d8` | Warm off-white surface for an occasional "ship's log" callout | — |
| `--parchment-ink` | `#2a2114` | Text color used ONLY on `--parchment` (12.8:1 AAA) | — |

**Rule:** `--brass` is never used as text on `--parchment` (1.9:1, fails)
— brass on parchment is decorative-only (a rule, a border, an icon
stroke). Text on parchment always uses `--parchment-ink`.

### Light mode (`prefers-color-scheme: light`)

Unchanged from the existing site — already accessibility-tested. `--brass`
in light mode uses a darker `#946f0f` (verified 4.6:1 on `#f6f7fb`) so the
same token stays legible when the OS/browser is in light mode; `--spectral`
is not used in light mode (it's a dark-theme-only glow effect).

## Typography

**No external font requests** — GhostMark's privacy stance (`PRIVACY.md`:
"No CDN JavaScript or remote fonts") is a hard constraint, so nothing
here adds a network request.

- **Body, controls, technical results, tables:** the existing system
  font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Inter,
  Roboto, sans-serif`) — unchanged. Developer readability comes first;
  this is already a good, fast, zero-dependency choice.
- **Display (logo, hero heading, "Captain's Log"-style section
  headings):** a serif system stack —
  `Georgia, "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif`
  — used with slightly increased letter-spacing for a restrained
  "ship's manifest / nautical chart" feel. Zero added assets, zero added
  network weight. Never used for body text, tables, or technical data.
- **Code, hashes, metadata values:**
  `ui-monospace, SFMono-Regular, "SF Mono", Consolas, "Liberation Mono", monospace`
  — new token (`--font-mono`), used anywhere a hash/technical value
  needs unambiguous character rendering.

## Spacing, radius, shadow

Extends the existing (already-consistent) scale rather than replacing it:

- Spacing: existing rem-based values (`0.3rem`/`0.5rem`/`0.75rem`/`1rem`/`1.5rem`/`2rem`) — an approximate 4/8pt rhythm already in use, kept as-is.
- Radius: `8px` (buttons, tabs, inputs), `10px` (panels), `12px` (cards) — existing scale, kept.
- Shadow: GhostMark's dark theme deliberately uses **border, not shadow**, for elevation (a shadow barely reads on a near-black background). New atmospheric elements (hero fog, illustration containers) use a soft `box-shadow: 0 0 40px rgba(0,0,0,0.4)` vignette only where it reinforces depth, never as a decorative flourish on ordinary cards.

## Icons & illustration

- **Style:** original, single-weight line art (1.5–2px stroke), using
  `currentColor` for the line and `--spectral` for an optional soft glow.
  No filled/outline mixing within one icon, no gradients, no
  photorealism, no copyrighted characters or franchise imagery.
- **Asset count:** a small, reused set (see `static/art/`), not one
  illustration per page:
  - `mascot-captain.svg` — the recurring GhostMark character (pirate
    captain silhouette + spyglass + a small ghost companion). Works at
    hero size and shrunk down for empty states.
  - `spyglass.svg` — inspection motif.
  - `ghost-mark.svg` — a single spectral ghost, used for "signal
    detected" moments and empty states.
  - `compass-rose.svg` — Lab / navigation-of-the-unknown motif.
  - `verify-seal.svg` — a wax-seal/stamp shape for the verification step.
  - `ship-harbor.svg` — a ship leaving a harbor, for the Run Local page.
  - `wave-divider.svg` — a low-key horizontal fog/wave motif for section
    breaks.
- **Decorative vs. meaningful:** every decorative SVG is inlined with
  `aria-hidden="true"` (or `<img alt="">` for the `<img>`-referenced
  versions) so screen readers skip it entirely. None of them carry
  information that isn't also present as real text.
- **Never encode status by shape/color alone** — every themed status
  icon sits next to the literal word (FOUND / VERIFIED / PARTIAL /
  UNKNOWN / PASS / FAIL), never instead of it.

## Motion

- Duration: 150–300ms for micro-interactions (button press, ghost
  fade-in/out, verdict badge stamp), matching `ui-ux-pro-max`'s
  animation guidance. Nothing loops indefinitely near technical results.
- Easing: `ease-out` for things entering/appearing, `ease-in` for things
  leaving/dissolving.
- **`prefers-reduced-motion: reduce` disables all decorative motion**
  (ghost fade, seal stamp, spyglass drift) — see `--motion-*` custom
  properties in `style.css`, gated behind a single media query so new
  animations can't be added without going through it.
- Only `transform`/`opacity` are animated (never `width`/`height`/`top`/`left`),
  so nothing here can cause layout shift.
- At most one decorative animation plays per state transition — e.g. the
  verdict badge "stamps" in once when verification completes; it does
  not also pulse, glow-loop, or bounce.

## What this system explicitly avoids

- Decorative pirate/ghost language inside machine-readable output
  (JSON receipts, `/api/*` responses, CLI `--json`) — theming is a
  presentation-layer concern only.
- Replacing precise technical terms (FOUND / NOT FOUND / UNKNOWN /
  VERIFIED CLEAN / PARTIAL / etc.) with in-theme language anywhere a
  user or a machine needs to read a real result.
- Turning providers (Claude, C2PA, EXIF, ...) into literal fictional
  map "islands" in the Lab — the capability matrix stays a plain,
  directly readable table; the pirate-map framing lives in the
  surrounding prose and header art, not the data.
- Emoji as icons (original SVG only).
- Any new external network request (fonts, CDN scripts, tracking).
