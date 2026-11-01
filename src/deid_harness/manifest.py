"""Ingest manifest for the Enron email corpus (CMU maildir release).

The manifest is the reconciliation baseline: one row per message with its hash,
headers, recipient counts, and word count. Every later stage (detection,
synthesis, file rebuild) reconciles back to these counts.

Layout expected: <root>/<mailbox>/<folder>/.../<n>.  (CMU files are named "1.", "2.", ...)
Note: the CMU release has attachments stripped, so attachment_count is usually 0;
the column stays so other corpora reconcile the same way.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Iterable, Iterator

from .textutil import sha256_bytes, word_count

FIELDS = [
    "rel_path", "mailbox", "folder", "sha256", "bytes", "message_id", "date",
    "from_addr", "to_count", "cc_count", "bcc_count", "subject",
    "body_words", "attachment_count", "parse_ok",
]

_PARSER = BytesParser(policy=policy.default)


@dataclass
class ManifestRow:
    rel_path: str
    mailbox: str
    folder: str
    sha256: str
    bytes: int
    message_id: str
    date: str
    from_addr: str
    to_count: int
    cc_count: int
    bcc_count: int
    subject: str
    body_words: int
    attachment_count: int
    parse_ok: bool


def _natural_key(path: Path) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", path.as_posix())]


def iter_message_files(root: Path, mailboxes: Iterable[str] | None = None) -> Iterator[Path]:
    """Yield message files in a stable order (mailbox, folder, natural file order)."""
    wanted = set(mailboxes) if mailboxes else None
    for box in sorted(p for p in root.iterdir() if p.is_dir()):
        if wanted is not None and box.name not in wanted:
            continue
        files = [p for p in box.rglob("*") if p.is_file() and not p.name.startswith(".")]
        yield from sorted(files, key=_natural_key)


def _count_addrs(msg: EmailMessage, header: str) -> int:
    values = msg.get_all(header, [])
    return len([a for _, a in getaddresses([str(v) for v in values]) if a])


def _body_text(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode("latin-1", errors="replace")


def build_row(path: Path, root: Path) -> ManifestRow:
    data = path.read_bytes()
    rel = path.relative_to(root)
    parts = rel.parts
    mailbox = parts[0]
    folder = "/".join(parts[1:-1])
    base = dict(rel_path=rel.as_posix(), mailbox=mailbox, folder=folder,
                sha256=sha256_bytes(data), bytes=len(data))
    try:
        msg = _PARSER.parsebytes(data)
        return ManifestRow(
            **base,
            message_id=str(msg.get("Message-ID", "")).strip(),
            date=str(msg.get("Date", "")).strip(),
            from_addr=", ".join(a for _, a in getaddresses([str(msg.get("From", ""))]) if a),
            to_count=_count_addrs(msg, "To"),
            cc_count=_count_addrs(msg, "Cc"),
            bcc_count=_count_addrs(msg, "Bcc"),
            subject=str(msg.get("Subject", "")).strip(),
            body_words=word_count(_body_text(msg)),
            attachment_count=sum(1 for _ in msg.iter_attachments()),
            parse_ok=True,
        )
    except Exception:  # keep the row so counts still reconcile
        return ManifestRow(**base, message_id="", date="", from_addr="", to_count=0,
                           cc_count=0, bcc_count=0, subject="", body_words=0,
                           attachment_count=0, parse_ok=False)


def build_manifest(root: str | Path, out_dir: str | Path,
                   mailboxes: Iterable[str] | None = None,
                   limit: int | None = None) -> dict:
    """Write manifest.csv and summary.json; return the summary."""
    root, out_dir = Path(root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"messages": 0, "bytes": 0, "body_words": 0, "recipients": 0,
               "attachments": 0, "parse_errors": 0, "duplicate_hashes": 0, "by_mailbox": {}}
    seen: set[str] = set()
    with (out_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for path in iter_message_files(root, mailboxes):
            if limit is not None and summary["messages"] >= limit:
                break
            row = build_row(path, root)
            writer.writerow(asdict(row))
            summary["messages"] += 1
            summary["bytes"] += row.bytes
            summary["body_words"] += row.body_words
            summary["recipients"] += row.to_count + row.cc_count + row.bcc_count
            summary["attachments"] += row.attachment_count
            summary["parse_errors"] += 0 if row.parse_ok else 1
            if row.sha256 in seen:
                summary["duplicate_hashes"] += 1
            seen.add(row.sha256)
            summary["by_mailbox"][row.mailbox] = summary["by_mailbox"].get(row.mailbox, 0) + 1
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
