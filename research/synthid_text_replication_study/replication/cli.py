"""CLI for the replication / robustness study.

    python -m replication.cli build-corpus --out datasets
    python -m replication.cli run    --config configs/default.yaml
    python -m replication.cli report --results results
"""

from __future__ import annotations

import argparse
import pathlib

import yaml


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="replication")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build-corpus")
    pb.add_argument("--out", default="datasets")
    pb.add_argument("--config", default="configs/default.yaml")
    pb.add_argument("--samples-per-bucket", type=int, default=2)

    pr = sub.add_parser("run")
    pr.add_argument("--config", default="configs/default.yaml")
    pr.add_argument("--results", default="results")

    prp = sub.add_parser("report")
    prp.add_argument("--results", default="results")

    args = p.parse_args(argv)

    if args.cmd == "build-corpus":
        from transformers import AutoTokenizer

        from .corpus_lengths import build_length_corpus
        cfg = yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8"))
        tok = AutoTokenizer.from_pretrained(cfg["model_name"], cache_dir=cfg["hf_cache_dir"])
        mp = build_length_corpus(pathlib.Path(args.out), tok, args.samples_per_bucket)
        print(f"wrote {mp}")
    elif args.cmd == "run":
        from .experiment import run
        csv = run(args.config, args.results)
        print(f"wrote {csv}")
        from .report import build_report
        print(f"wrote {build_report(pathlib.Path(args.results))}")
    elif args.cmd == "report":
        from .report import build_report
        print(f"wrote {build_report(pathlib.Path(args.results))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
