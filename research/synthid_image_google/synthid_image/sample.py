"""Deterministic synthetic images for offline demo/tests.

These are NOT SynthID-watermarked and are NOT Google images -- they exist only
so the transform/metrics/experiment pipeline can run without any API. Real
benchmarks use genuine Imagen/Vertex images (gitignored).
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def synthetic_image(seed: int = 0, size: int = 256) -> Image.Image:
    """A smooth gradient + deterministic shapes, no randomness beyond `seed`."""
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float64)
    r = (xs / size * 255).astype(np.uint8)
    g = (ys / size * 255).astype(np.uint8)
    b = (((xs + ys + seed * 37) % size) / size * 255).astype(np.uint8)
    arr = np.dstack([r, g, b]).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    return img
