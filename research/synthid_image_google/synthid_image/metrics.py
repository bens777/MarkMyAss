"""Quality metrics: SSIM and PSNR (numpy only, no scipy/scikit-image).

For geometry-changing transforms (resize/crop) the transformed image is first
resized back to the original dimensions before comparison, so the number is an
approximate perceptual similarity, not a pixel-exact one. Callers should flag
`geometry_changing` alongside the metric.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.float64)


def _align(a: Image.Image, b: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    if b.size != a.size:
        b = b.resize(a.size, Image.LANCZOS)
    return _rgb_array(a), _rgb_array(b)


def psnr(a: Image.Image, b: Image.Image) -> float:
    xa, xb = _align(a, b)
    mse = float(np.mean((xa - xb) ** 2))
    if mse == 0.0:
        return 100.0
    return float(10.0 * np.log10((255.0 ** 2) / mse))


def _box_mean(a: np.ndarray, win: int) -> np.ndarray:
    ii = np.cumsum(np.cumsum(a, axis=0), axis=1)
    ii = np.pad(ii, ((1, 0), (1, 0)))
    s = ii[win:, win:] - ii[:-win, win:] - ii[win:, :-win] + ii[:-win, :-win]
    return s / (win * win)


def ssim(a: Image.Image, b: Image.Image, win: int = 7) -> float:
    """Mean windowed SSIM on the luminance channel, values scaled to [0, 1]."""
    xa, xb = _align(a, b)
    # luminance (Rec. 601), normalised to [0, 1]
    x = (xa @ np.array([0.299, 0.587, 0.114])) / 255.0
    y = (xb @ np.array([0.299, 0.587, 0.114])) / 255.0
    if min(x.shape) < win:
        win = max(1, min(x.shape))
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    mux, muy = _box_mean(x, win), _box_mean(y, win)
    mxx, myy = _box_mean(x * x, win), _box_mean(y * y, win)
    mxy = _box_mean(x * y, win)
    vx, vy = mxx - mux * mux, myy - muy * muy
    vxy = mxy - mux * muy
    num = (2 * mux * muy + c1) * (2 * vxy + c2)
    den = (mux * mux + muy * muy + c1) * (vx + vy + c2)
    return float(np.mean(num / den))


def dims(img: Image.Image) -> tuple[int, int]:
    return int(img.size[0]), int(img.size[1])
