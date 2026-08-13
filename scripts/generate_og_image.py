"""Generates GhostMark's single shared Open Graph / Twitter card image.

Original artwork only -- a simple geometric ghost mark drawn with plain
PIL primitives (no external assets, no AI image generation, nothing that
could carry someone else's copyright). Uses Pillow, already a project
dependency (see pyproject.toml). Re-run this after changing the design:

    python scripts/generate_og_image.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_PATH = Path(__file__).parent.parent / "src" / "ghostmark" / "web" / "static" / "og-image.png"

WIDTH, HEIGHT = 1200, 630
BG = (15, 17, 21)
GHOST_FILL = (231, 233, 238)
GHOST_EYE = (15, 17, 21)
ACCENT = (124, 140, 255)
MUTED = (154, 161, 173)


def _ghost_polygon(cx: int, cy: int, r: int, scallops: int = 5) -> list[tuple[int, int]]:
    """A rounded-top, scalloped-bottom silhouette -- the classic ghost shape,
    built entirely from arithmetic, no image tracing."""

    points: list[tuple[int, int]] = []
    # Top semicircle (180 degrees), left to right.
    for deg in range(180, -1, -6):
        rad = math.radians(deg)
        points.append((cx + r * math.cos(rad), cy - r * math.sin(rad)))
    # Right side down to the scalloped hem.
    hem_y = cy + r
    points.append((cx + r, hem_y - r * 0.15))
    # Scalloped bottom, right to left.
    scallop_w = (2 * r) / scallops
    for i in range(scallops + 1):
        x = cx + r - i * scallop_w
        y = hem_y if i % 2 == 0 else hem_y - r * 0.22
        points.append((x, y))
    points.append((cx - r, hem_y - r * 0.15))
    return [(round(x), round(y)) for x, y in points]


def build() -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    ghost_cx, ghost_cy, ghost_r = 230, 300, 130
    draw.polygon(_ghost_polygon(ghost_cx, ghost_cy, ghost_r), fill=GHOST_FILL)
    eye_dy, eye_dx, eye_r = -15, 45, 12
    draw.ellipse(
        (ghost_cx - eye_dx - eye_r, ghost_cy + eye_dy - eye_r, ghost_cx - eye_dx + eye_r, ghost_cy + eye_dy + eye_r),
        fill=GHOST_EYE,
    )
    draw.ellipse(
        (ghost_cx + eye_dx - eye_r, ghost_cy + eye_dy - eye_r, ghost_cx + eye_dx + eye_r, ghost_cy + eye_dy + eye_r),
        fill=GHOST_EYE,
    )

    title_font = ImageFont.load_default(size=88)
    tagline_font = ImageFont.load_default(size=34)
    sub_font = ImageFont.load_default(size=28)

    text_x = 430
    draw.text((text_x, 235), "GhostMark", font=title_font, fill=GHOST_FILL)
    draw.text((text_x, 345), "Proof, not promises.", font=tagline_font, fill=ACCENT)
    draw.text(
        (text_x, 400),
        "Claude Watermark Remover & AI Metadata Cleaner",
        font=sub_font,
        fill=MUTED,
    )

    return img


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    build().save(OUT_PATH, format="PNG", optimize=True)
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
