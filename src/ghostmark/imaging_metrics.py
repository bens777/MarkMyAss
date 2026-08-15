"""Image similarity metrics: SSIM, PSNR, and pixel-change percentage.

Pure NumPy over Pillow images -- no scipy/scikit-image, no ML. Used to show a
user how much a reprocessed image changed. These describe pixel-level
difference; they are NOT proof of visual identity, and the UI must not present
them as such.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

# SSIM is computed on a bounded-resolution luminance copy so it stays fast on
# large photos; PSNR / pixel-change run at full resolution (cheap in NumPy).
_SSIM_MAX_DIM = 2048


def _rgb(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.float64)


def _aligned(a: Image.Image, b: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    if b.size != a.size:
        b = b.resize(a.size, Image.LANCZOS)
    return _rgb(a), _rgb(b)


def psnr(a: Image.Image, b: Image.Image) -> float:
    xa, xb = _aligned(a, b)
    mse = float(np.mean((xa - xb) ** 2))
    if mse == 0.0:
        return 100.0
    return float(min(100.0, 10.0 * np.log10((255.0**2) / mse)))


def pixel_changed_pct(a: Image.Image, b: Image.Image, threshold: int = 2) -> float:
    """Percentage of pixels where any RGB channel differs by more than `threshold`."""
    xa, xb = _aligned(a, b)
    diff = np.abs(xa - xb).max(axis=2)
    changed = float(np.count_nonzero(diff > threshold))
    total = diff.size or 1
    return 100.0 * changed / total


def _box_mean(a: np.ndarray, win: int) -> np.ndarray:
    ii = np.cumsum(np.cumsum(a, axis=0), axis=1)
    ii = np.pad(ii, ((1, 0), (1, 0)))
    s = ii[win:, win:] - ii[:-win, win:] - ii[win:, :-win] + ii[:-win, :-win]
    return s / (win * win)


def ssim(a: Image.Image, b: Image.Image, win: int = 7) -> float:
    """Mean windowed SSIM on luminance, in [0, 1] (1.0 == identical)."""
    if b.size != a.size:
        b = b.resize(a.size, Image.LANCZOS)
    # bound resolution for speed on large images
    w, h = a.size
    scale = min(1.0, _SSIM_MAX_DIM / max(w, h))
    if scale < 1.0:
        size = (max(1, round(w * scale)), max(1, round(h * scale)))
        a = a.resize(size, Image.LANCZOS)
        b = b.resize(size, Image.LANCZOS)
    xa = _rgb(a) @ np.array([0.299, 0.587, 0.114]) / 255.0
    xb = _rgb(b) @ np.array([0.299, 0.587, 0.114]) / 255.0
    if min(xa.shape) < win:
        win = max(1, min(xa.shape))
    c1, c2 = 0.01**2, 0.03**2
    mux, muy = _box_mean(xa, win), _box_mean(xb, win)
    vx = _box_mean(xa * xa, win) - mux * mux
    vy = _box_mean(xb * xb, win) - muy * muy
    vxy = _box_mean(xa * xb, win) - mux * muy
    num = (2 * mux * muy + c1) * (2 * vxy + c2)
    den = (mux * mux + muy * muy + c1) * (vx + vy + c2)
    return float(np.clip(np.mean(num / den), 0.0, 1.0))
