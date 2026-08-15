"""Command-line entry point for the SynthID-Text behaviour study.

    python -m synthid_study.cli run    --config configs/default.yaml
    python -m synthid_study.cli report --results results
"""

from __future__ import annotations

import argparse
import pathlib


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synthid_study")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the full experiment grid")
    p_run.add_argument("--config", default="configs/default.yaml")
    p_run.add_argument("--results", default="results")

    p_rep = sub.add_parser("report", help="build report.md + charts from results")
    p_rep.add_argument("--results", default="results")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        from .experiment import run

        csv_path = run(args.config, args.results)
        print(f"wrote {csv_path}")
        from .report import build_report

        rep = build_report(pathlib.Path(args.results))
        print(f"wrote {rep}")
    elif args.cmd == "report":
        from .report import build_report

        rep = build_report(pathlib.Path(args.results))
        print(f"wrote {rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
