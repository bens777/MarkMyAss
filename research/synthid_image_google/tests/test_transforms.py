"""Transform pipeline behaviour (no API)."""

from PIL import Image
from synthid_image import transforms as T
from synthid_image.sample import synthetic_image


def _img():
    return synthetic_image(seed=1, size=128)


def test_build_set_covers_required_families():
    names = [t.name for t in T.build_transform_set()]
    assert {"screenshot_x1", "screenshot_x2", "screenshot_x5", "screenshot_x10"} <= set(names)
    assert any(n.startswith("jpeg_q") for n in names)
    assert any(n.startswith("resize_") for n in names)
    assert any(n.startswith("crop_") for n in names)
    assert {"convert_png", "convert_jpeg", "convert_webp"} <= set(names)
    assert any(n.startswith("bc_") for n in names)


def test_every_transform_returns_an_image():
    img = _img()
    for t in T.build_transform_set():
        out = t.apply(img)
        assert isinstance(out, Image.Image)
        assert out.size[0] > 0 and out.size[1] > 0


def test_crop_and_resize_change_dimensions():
    img = _img()
    assert T.center_crop(img, 0.5).size == (64, 64)
    assert T.resize_scale(img, 0.5).size == (64, 64)
    assert T.resize_scale(img, 1.5).size == (192, 192)


def test_screenshot_iterations_are_deterministic():
    img = _img()
    a = T.repeated_rerender(img, 3)
    b = T.repeated_rerender(img, 3)
    assert a.tobytes() == b.tobytes()


def test_jpeg_and_format_roundtrips_run():
    img = _img()
    assert T.jpeg_quality(img, 50).size == img.size
    assert T.format_chain(img, ["PNG", "JPEG", "WEBP"]).size == img.size
