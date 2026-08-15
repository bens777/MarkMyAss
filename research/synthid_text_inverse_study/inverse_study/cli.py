"""CLI for the inverse SynthID-Text study.

    python -m inverse_study.cli build-corpus [--out datasets]
    python -m inverse_study.cli run    --config configs/default.yaml
    python -m inverse_study.cli report --results results
"""

from __future__ import annotations

import argparse
import pathlib


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="inverse_study")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build-corpus", help="download + slice the public-domain corpus")
    pb.add_argument("--out", default="datasets")
    pb.add_argument("--samples-per-work", type=int, default=4)

    pr = sub.add_parser("run", help="run the full grid")
    pr.add_argument("--config", default="configs/default.yaml")
    pr.add_argument("--results", default="results")

    prp = sub.add_parser("report", help="build report.md + charts")
    prp.add_argument("--results", default="results")

    args = p.parse_args(argv)

    if args.cmd == "build-corpus":
        from .corpus import build_corpus
        mp = build_corpus(pathlib.Path(args.out), samples_per_work=args.samples_per_work)
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
