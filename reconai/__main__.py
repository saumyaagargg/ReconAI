"""Run with:  python -m reconai [--data-dir data] [--out-dir output]"""
import argparse
import os

from .config import DEFAULT_GEMINI_MODEL
from .engine import run


def main():
    parser = argparse.ArgumentParser(description="Reconcile bank statement against internal ledger.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    report, queue = run(args.data_dir, args.out_dir, api_key=api_key, model=model)

    methods = {}
    for m in report["matches"]:
        methods[m["method"]] = methods.get(m["method"], 0) + 1
    print(f"Match rate: {report['match_rate_pct']}% "
          f"({report['matched_bank_rows']}/{report['total_bank_rows']} bank rows matched)")
    print("Matched via:", ", ".join(f"{k}={v}" for k, v in sorted(methods.items())) or "none")
    print(f"Unmatched exceptions: {len(report['exceptions'])}")
    print(f"Review queue: {len(queue)} candidate pairs awaiting human review")
    if not api_key:
        print("Note: GEMINI_API_KEY not set, so ambiguous cases have no AI suggestion.")
    print(f"Written to {args.out_dir}/")


if __name__ == "__main__":
    main()