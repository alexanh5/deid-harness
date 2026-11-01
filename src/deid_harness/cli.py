"""Command line entry point: `deid manifest ...`, `deid usage ...`."""

from __future__ import annotations

import argparse
import json
import sys

from .cache import ResponseCache
from .manifest import build_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deid")
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("manifest", help="Build the ingest manifest for a maildir corpus")
    m.add_argument("root", help="Path to the maildir folder (e.g. data/enron/maildir)")
    m.add_argument("--out", default="data/manifest", help="Output folder (default: data/manifest)")
    m.add_argument("--mailbox", action="append", help="Limit to a mailbox; repeat for several")
    m.add_argument("--limit", type=int, help="Stop after this many messages")

    u = sub.add_parser("usage", help="Words sent to engines on cache misses")
    u.add_argument("--cache", default="cache", help="Cache folder (default: cache)")
    u.add_argument("--engine", help="Only this engine")

    args = parser.parse_args(argv)
    if args.command == "manifest":
        summary = build_manifest(args.root, args.out, args.mailbox, args.limit)
        json.dump(summary, sys.stdout, indent=2)
        print()
    elif args.command == "usage":
        print(ResponseCache(args.cache).words_used(args.engine))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
