"""CLI for the Google SynthID image benchmark.

    python -m synthid_image.cli demo
    python -m synthid_image.cli run    --config configs/default.yaml   # offline mock
    python -m synthid_image.cli report --results results/mock
    python -m synthid_image.cli pilot  --config configs/default.yaml --project MY_GCP_PROJECT \
        --enable-paid                                                   # PAID, gated (see below)

The `pilot` command is the ONLY one that can make paid calls, and only when
`--enable-paid` is passed AND live Vertex credentials/SDK are present. Without
those it records DETECTOR_UNAVAILABLE rows (no call, no fabricated result).
"""

from __future__ import annotations

import argparse
import pathlib

import yaml

from . import metrics
from .detector import MockVertexDetector, VertexImagenDetector
from .experiment import _load_sources, run
from .report import build_report
from .sample import synthetic_image
from .transforms import build_transform_set


def _cfg(path):
    return yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))


def _synthetic_sources(n: int):
    return [(f"synthetic_{i}", synthetic_image(seed=i)) for i in range(n)]


def cmd_demo(args):
    img = synthetic_image(seed=0)
    print(f"{'transform':22} {'SSIM':>7} {'PSNR':>7} {'dims':>12}")
    for t in build_transform_set():
        out = t.apply(img)
        print(f"{t.name:22} {metrics.ssim(img, out):7.3f} {metrics.psnr(img, out):7.2f} "
              f"{str(metrics.dims(out)):>12}")
    return 0


def cmd_run(args):
    cfg = _cfg(args.config)
    src_dir = pathlib.Path(cfg.get("source_images_dir", "datasets/sources"))
    sources = _load_sources(src_dir) or _synthetic_sources(cfg.get("mock_synthetic_sources", 2))
    out = pathlib.Path(args.results or "results/mock")
    csv = run(sources, MockVertexDetector(), out,
              price_per_call_usd=0.0, provider="synthetic-mock", model="n/a")
    print(f"wrote {csv}")
    print(f"wrote {build_report(out)}")
    return 0


def cmd_report(args):
    print(f"wrote {build_report(pathlib.Path(args.results))}")
    return 0


def cmd_pilot(args):
    cfg = _cfg(args.config)
    vcfg = cfg.get("detector", {}).get("vertex", {})
    price = float(vcfg.get("price_per_call_usd", 0.0))
    max_images = min(int(cfg.get("max_pilot_images", 10)), 10)  # hard cap 10

    src_dir = pathlib.Path(args.sources or cfg.get("pilot_sources_dir", "datasets/pilot_sources"))
    sources = _load_sources(src_dir)
    if not sources:
        print(f"ERROR: no pilot source images in {src_dir}. Add genuine Imagen/Vertex images "
              f"(watermark on by default) before running the pilot.")
        return 2
    sources = sources[:max_images]

    n_calls = len(sources) * (1 + len(build_transform_set()))
    print(f"PILOT: {len(sources)} images (cap {max_images}) -> ~{n_calls} verify calls; "
          f"price/call ${price} -> est. ${n_calls * price:.4f}")
    if args.enable_paid and not args.project:
        print("ERROR: --enable-paid requires --project")
        return 2
    if not args.enable_paid:
        print("NOTE: --enable-paid NOT set -> no paid calls; rows will be DETECTOR_UNAVAILABLE.")

    detector = VertexImagenDetector(project=args.project, location=vcfg.get("location", "us-central1"),
                                    enable_paid=args.enable_paid, price_per_call_usd=price)
    out = pathlib.Path(args.results or "results/pilot")
    csv = run(sources, detector, out, price_per_call_usd=price,
              provider="google-imagen", model=vcfg.get("model", "imagen"))
    print(f"wrote {csv}")
    print(f"wrote {build_report(out)}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="synthid_image")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo").set_defaults(func=cmd_demo)

    pr = sub.add_parser("run")
    pr.add_argument("--config", default="configs/default.yaml")
    pr.add_argument("--results", default=None)
    pr.set_defaults(func=cmd_run)

    prp = sub.add_parser("report")
    prp.add_argument("--results", default="results/mock")
    prp.set_defaults(func=cmd_report)

    pp = sub.add_parser("pilot")
    pp.add_argument("--config", default="configs/default.yaml")
    pp.add_argument("--project", default=None)
    pp.add_argument("--sources", default=None)
    pp.add_argument("--results", default=None)
    pp.add_argument("--enable-paid", action="store_true",
                    help="REQUIRED to make paid Vertex calls; also needs --project + credentials")
    pp.set_defaults(func=cmd_pilot)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
