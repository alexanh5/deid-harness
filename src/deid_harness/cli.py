"""Command line entry point: `deid manifest ...`, `deid sample ...`, `deid usage ...`."""

from __future__ import annotations

import argparse
import json
import sys

from .cache import ResponseCache
from .manifest import build_manifest
from .sample import SampleExistsError, build_sample


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deid")
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("manifest", help="Build the ingest manifest for a maildir corpus")
    m.add_argument("root", help="Path to the maildir folder (e.g. data/enron/maildir)")
    m.add_argument("--out", default="data/manifest", help="Output folder (default: data/manifest)")
    m.add_argument("--mailbox", action="append", help="Limit to a mailbox; repeat for several")
    m.add_argument("--limit", type=int, help="Stop after this many messages")

    s = sub.add_parser("sample", help="Draw the labeling sample and write Label Studio tasks")
    s.add_argument("root", help="Path to the maildir folder (e.g. data/raw/maildir)")
    s.add_argument("--out", default="data/labeling", help="Output folder (default: data/labeling)")
    s.add_argument("--mailbox", action="append", help="Limit to a mailbox; repeat for several")
    s.add_argument("--n", type=int, default=100, help="Messages to draw (default: 100)")
    s.add_argument("--max-words", type=int, default=400, help="Max body words (default: 400)")
    s.add_argument("--seed", type=int, default=20261101, help="Random seed (default: 20261101)")
    s.add_argument("--force", action="store_true", help="Replace an existing sample")

    u = sub.add_parser("usage", help="Words sent to engines on cache misses")
    u.add_argument("--cache", default="cache", help="Cache folder (default: cache)")
    u.add_argument("--engine", help="Only this engine")

    args = parser.parse_args(argv)
    if args.command == "manifest":
        summary = build_manifest(args.root, args.out, args.mailbox, args.limit)
        json.dump(summary, sys.stdout, indent=2)
        print()
    elif args.command == "sample":
        try:
            summary = build_sample(args.root, args.out, args.mailbox, args.n,
                                   args.max_words, args.seed, args.force)
        except SampleExistsError as exc:
            print(f"deid sample: {exc}", file=sys.stderr)
            return 1
        json.dump(summary, sys.stdout, indent=2)
        print()
    elif args.command == "usage":
        print(ResponseCache(args.cache).words_used(args.engine))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
