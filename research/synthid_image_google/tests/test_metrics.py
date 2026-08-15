"""SSIM / PSNR metrics (no API)."""

from synthid_image import metrics
from synthid_image.sample import synthetic_image
from synthid_image.transforms import center_crop, jpeg_quality


def test_identical_image_scores_max():
    img = synthetic_image(seed=2, size=128)
    assert metrics.ssim(img, img) > 0.999
    assert metrics.psnr(img, img) == 100.0


def test_degraded_image_scores_lower():
    img = synthetic_image(seed=2, size=128)
    deg = jpeg_quality(img, 20)
    assert metrics.ssim(img, deg) < 0.999
    assert metrics.psnr(img, deg) < 100.0


def test_metrics_handle_size_mismatch():
    img = synthetic_image(seed=2, size=128)
    cropped = center_crop(img, 0.5)  # different dims
    s = metrics.ssim(img, cropped)   # aligned internally
    p = metrics.psnr(img, cropped)
    assert 0.0 <= s <= 1.0
    assert p > 0.0
