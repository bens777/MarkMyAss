"""Run the transform benchmark: verify baseline, transform, re-verify, record.

No API call is made by the transform/metrics code. The only calls come from the
injected DetectorAdapter; with the mock or an unconfigured Vertex adapter those
are free / DETECTOR_UNAVAILABLE.
"""

from __future__ import annotations

import json
import pathlib
import time
from typing import Any

import pandas as pd
from PIL import Image

from . import metrics
from .detector import DetectorAdapter
from .schema import COLUMNS
from .transforms import Transform, build_transform_set


def _load_sources(source_dir: pathlib.Path) -> list[tuple[str, Image.Image]]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    out = []
    if source_dir.is_dir():
        for p in sorted(source_dir.iterdir()):
            if p.suffix.lower() in exts:
                out.append((p.stem, Image.open(p).copy()))
    return out


def run(
    sources: list[tuple[str, Image.Image]],
    detector: DetectorAdapter,
    out_dir: pathlib.Path,
    price_per_call_usd: float = 0.0,
    provider: str = "synthetic-mock",
    model: str = "n/a",
    transforms: list[Transform] | None = None,
) -> pathlib.Path:
    out_dir = pathlib.Path(out_dir)
    tdir = out_dir / "transformed"
    tdir.mkdir(parents=True, exist_ok=True)
    transforms = transforms if transforms is not None else build_transform_set()

    rows: list[dict[str, Any]] = []
    exp_id = 0
    for sid, img in sources:
        img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
        # Baseline verification of the untouched source (1 call).
        base = detector.verify(_save(img, tdir / f"{sid}__baseline.png"))
        w, h = metrics.dims(img)
        rows.append(_row(exp_id, sid, provider, model, "__baseline__", {}, 1,
                         base, base, 1.0, 100.0, w, h,
                         (tdir / f"{sid}__baseline.png").stat().st_size, 0.0,
                         price_per_call_usd))
        exp_id += 1

        for t in transforms:
            t0 = time.time()
            tim = t.apply(img)
            path = _save(tim, tdir / f"{sid}__{t.name}.{t.out_format.lower()}", t.out_format)
            runtime_ms = (time.time() - t0) * 1000.0
            after = detector.verify(path)   # 1 call
            ssim = metrics.ssim(img, tim)
            psnr = metrics.psnr(img, tim)
            tw, th = metrics.dims(tim)
            rows.append(_row(exp_id, sid, provider, model, t.name, t.params, t.iterations,
                             base, after, ssim, psnr, tw, th,
                             pathlib.Path(path).stat().st_size, runtime_ms,
                             price_per_call_usd))
            exp_id += 1

    df = pd.DataFrame(rows, columns=COLUMNS)
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "summary.csv", index=False)
    total_cost = float(df["estimated_api_cost_usd"].sum())
    (out_dir / "summary.json").write_text(json.dumps({
        "n_rows": len(df), "n_sources": len(sources),
        "detector_provider": detector.provider, "detector": detector.detector,
        "price_per_call_usd": price_per_call_usd,
        "estimated_total_cost_usd": round(total_cost, 4),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2), encoding="utf-8")
    return out_dir / "summary.csv"


def _save(img: Image.Image, path: pathlib.Path, fmt: str | None = None) -> str:
    path = pathlib.Path(path)
    fmt = (fmt or path.suffix.lstrip(".")).upper()
    fmt = "JPEG" if fmt in ("JPG", "JPEG") else fmt
    save_img = img if fmt == "PNG" else img.convert("RGB")
    save_img.save(path, format=fmt)
    return str(path)


def _row(exp_id, sid, provider, model, tname, params, iters, before, after,
         ssim, psnr, w, h, size, runtime_ms, price) -> dict[str, Any]:
    row = {c: None for c in COLUMNS}
    row.update({
        "experiment_id": exp_id, "source_image_id": sid, "provider": provider,
        "model": model, "transform": tname, "parameters": json.dumps(params),
        "iteration_count": iters,
        "verifier_before_status": before.status.value,
        "verifier_before_detected": before.detected,
        "verifier_before_confidence": before.confidence,
        "verifier_after_status": after.status.value,
        "verifier_after_detected": after.detected,
        "verifier_after_confidence": after.confidence,
        "verifier_raw_before": json.dumps(before.raw_result),
        "verifier_raw_after": json.dumps(after.raw_result),
        "ssim": round(float(ssim), 5), "psnr": round(float(psnr), 3),
        "width": w, "height": h, "file_size_bytes": int(size),
        "runtime_ms": round(float(runtime_ms), 2),
        "estimated_api_cost_usd": round(price, 6),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    return row
