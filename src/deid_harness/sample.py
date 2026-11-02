"""Draw the labeling sample from a maildir corpus.

Steps, each counted in sample_summary.json so the sample reconciles to the manifest:
  1. Parse every message in the selected mailboxes (same walk order as the manifest).
  2. Normalize the body: NFC, "\\n" line endings, trailing whitespace stripped per line,
     leading and trailing blank lines removed. This normalized text is the single
     source for labeling AND for every engine; offsets are only valid against it.
  3. Drop parse failures and empty bodies.
  4. De-duplicate on sender + subject + first body line (Enron copies the same email
     across sent, sent_items, and all_documents). The first copy in walk order wins.
  5. Keep bodies with at most `max_words` words.
  6. Draw `n` with a fixed seed, then order by rel_path so the output is stable.

Outputs in out_dir:
  texts/<sample_id>.txt   normalized body, UTF-8, written byte for byte
  tasks.json              Label Studio import (data: text, message_id, sample_id, rel_path, text_sha256)
  sample.csv              one row per sampled message
  sample_summary.json     counts at each step, parameters, total words
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import unicodedata
from pathlib import Path
from typing import Iterable

from .manifest import _PARSER, _body_text, iter_message_files
from .textutil import word_count

SAMPLE_FIELDS = ["sample_id", "rel_path", "message_id", "from_addr", "subject",
                 "body_words", "text_sha256"]


class SampleExistsError(RuntimeError):
    """Raised when the output folder already holds a sample and force is off."""


def normalize_body(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def sample_id_for(rel_path: str) -> str:
    """allen-p/sent/12. -> allen-p__sent__12 (file-name safe, readable, unique per file)."""
    return rel_path.rstrip(".").replace("/", "__")


def dedupe_key(from_addr: str, subject: str, body: str) -> tuple[str, str, str]:
    first_line = next((ln.strip() for ln in body.split("\n") if ln.strip()), "")
    return (from_addr.strip().lower(), " ".join(subject.split()).lower(), first_line.lower())


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_sample(root: str | Path, out_dir: str | Path,
                 mailboxes: Iterable[str] | None = None, n: int = 100,
                 max_words: int = 400, seed: int = 20261101,
                 force: bool = False) -> dict:
    root, out_dir = Path(root), Path(out_dir)
    if (out_dir / "tasks.json").exists() and not force:
        raise SampleExistsError(
            f"{out_dir / 'tasks.json'} already exists. Labels depend on this exact sample; "
            "pass --force only if you mean to replace it.")

    counts = {"scanned": 0, "parse_errors": 0, "empty_bodies": 0,
              "duplicates_removed": 0, "over_max_words": 0, "eligible": 0}
    seen: set[tuple[str, str, str]] = set()
    eligible: list[dict] = []

    for path in iter_message_files(root, mailboxes):
        counts["scanned"] += 1
        rel = path.relative_to(root).as_posix()
        try:
            msg = _PARSER.parsebytes(path.read_bytes())
            body = normalize_body(_body_text(msg))
            from_addr = str(msg.get("From", "")).strip()
            subject = str(msg.get("Subject", "")).strip()
            message_id = str(msg.get("Message-ID", "")).strip()
        except Exception:
            counts["parse_errors"] += 1
            continue
        if not body:
            counts["empty_bodies"] += 1
            continue
        key = dedupe_key(from_addr, subject, body)
        if key in seen:
            counts["duplicates_removed"] += 1
            continue
        seen.add(key)
        words = word_count(body)
        if words > max_words:
            counts["over_max_words"] += 1
            continue
        eligible.append(dict(sample_id=sample_id_for(rel), rel_path=rel, message_id=message_id,
                             from_addr=from_addr, subject=subject, body_words=words,
                             text=body, text_sha256=text_sha256(body)))

    counts["eligible"] = len(eligible)
    drawn = random.Random(seed).sample(eligible, min(n, len(eligible)))
    drawn.sort(key=lambda r: r["rel_path"])

    texts_dir = out_dir / "texts"
    texts_dir.mkdir(parents=True, exist_ok=True)
    for old in texts_dir.glob("*.txt"):
        old.unlink()
    tasks = []
    for r in drawn:
        (texts_dir / f"{r['sample_id']}.txt").write_bytes(r["text"].encode("utf-8"))
        tasks.append({"data": {k: r[k] for k in
                               ("text", "message_id", "sample_id", "rel_path", "text_sha256")}})
    (out_dir / "tasks.json").write_text(json.dumps(tasks, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    with (out_dir / "sample.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SAMPLE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(drawn)

    summary = {**counts, "sampled": len(drawn), "requested": n, "seed": seed,
               "max_words": max_words, "mailboxes": sorted(mailboxes) if mailboxes else "all",
               "sampled_words": sum(r["body_words"] for r in drawn)}
    (out_dir / "sample_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
