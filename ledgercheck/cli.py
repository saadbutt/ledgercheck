"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .generate import write_corpus
from .validate import validate

DEFAULT_ROOT = Path("corpus")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ledgercheck", description="Build and check the corpus.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="regenerate the documents and the truth files")
    build.add_argument("--root", type=Path, default=DEFAULT_ROOT)

    check = sub.add_parser("validate", help="check the corpus against its own invariants")
    check.add_argument("--root", type=Path, default=DEFAULT_ROOT)

    show = sub.add_parser("summary", help="print what the corpus contains")
    show.add_argument("--root", type=Path, default=DEFAULT_ROOT)

    args = parser.parse_args(argv)

    if args.command == "build":
        summary = write_corpus(args.root)
        print(f"{summary['document_count']} documents, {summary['card_charge_count']} card charges")
        print(f"written to {args.root}")
        return 0

    if args.command == "validate":
        problems = validate(args.root)
        if not problems:
            print("corpus is consistent")
            return 0
        for problem in problems:
            print(f"FAIL  {problem}")
        print(f"\n{len(problems)} problem(s)")
        return 1

    summary = json.loads((args.root / "corpus.json").read_text())
    period = f"{summary['period'][0]} to {summary['period'][1]}"
    print(f"{summary['store']}, {period}, books in {summary['books_currency']}")
    print(f"{summary['document_count']} documents, {summary['card_charge_count']} card charges\n")
    width = max(len(k) for k in summary["cases"])
    for name, description in summary["cases"].items():
        ids = ", ".join(summary["case_doc_ids"].get(name, []))
        print(f"{name:<{width}}  {description}")
        print(f"{'':<{width}}  {ids}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
