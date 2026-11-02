"""Tests for `deid sample`. Each test builds a tiny maildir in tmp_path (invented people only)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from deid_harness.cli import main
from deid_harness.sample import SampleExistsError, build_sample, normalize_body


def _write(root: Path, rel: str, frm: str, subject: str, body: str, mid: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (f"Message-ID: <{mid}@example.com>\r\nDate: Wed, 16 May 2001 11:20:00 -0700 (PDT)\r\n"
         f"From: {frm}\r\nTo: jane.doe@example.com\r\nSubject: {subject}\r\n"
         "Mime-Version: 1.0\r\nContent-Type: text/plain; charset=us-ascii\r\n\r\n"
         f"{body}").encode("ascii"))


@pytest.fixture
def maildir(tmp_path: Path) -> Path:
    root = tmp_path / "maildir"
    _write(root, "doe-j/sent/1.", "jane.doe@example.com", "Q3 plan", "Hi Sam,\r\nSee attached.   \r\n", "1")
    # Same email copied into another folder: removed as a duplicate.
    _write(root, "doe-j/all_documents/1.", "jane.doe@example.com", "Q3 plan", "Hi Sam,\r\nSee attached.\r\n", "2")
    _write(root, "doe-j/sent/2.", "jane.doe@example.com", "Long", "word " * 450, "3")
    _write(root, "doe-j/inbox/1.", "sam.roe@example.com", "Empty", "\r\n\r\n", "4")
    for i in range(3, 8):
        _write(root, f"doe-j/sent/{i}.", "jane.doe@example.com", f"Note {i}", f"Call me at ext {i}.", f"n{i}")
    _write(root, "roe-s/inbox/1.", "sam.roe@example.com", "Other box", "Not in the sample.", "9")
    return root


def test_normalize_body():
    assert normalize_body("\r\n\r\nHi  \r\nthere\t\r\n\r\n") == "Hi\nthere"
    assert normalize_body("Café") == "Café"  # NFC


def test_counts_reconcile(maildir: Path, tmp_path: Path):
    s = build_sample(maildir, tmp_path / "out", ["doe-j"], n=100)
    assert s["scanned"] == 9
    assert (s["parse_errors"], s["empty_bodies"], s["duplicates_removed"], s["over_max_words"]) == (0, 1, 1, 1)
    assert s["eligible"] == 6 and s["sampled"] == 6
    assert s["scanned"] == (s["parse_errors"] + s["empty_bodies"] + s["duplicates_removed"]
                            + s["over_max_words"] + s["eligible"])


def test_texts_match_tasks_byte_for_byte(maildir: Path, tmp_path: Path):
    out = tmp_path / "out"
    build_sample(maildir, out, ["doe-j"])
    tasks = json.loads((out / "tasks.json").read_text(encoding="utf-8"))
    for t in tasks:
        d = t["data"]
        raw = (out / "texts" / f"{d['sample_id']}.txt").read_bytes()
        assert raw == d["text"].encode("utf-8")
        assert hashlib.sha256(raw).hexdigest() == d["text_sha256"]
        assert b"\r" not in raw
    # Folders walk alphabetically, so the all_documents copy is the one kept.
    first = next(t["data"] for t in tasks if t["data"]["text"].startswith("Hi Sam"))
    assert first["text"] == "Hi Sam,\nSee attached."
    assert first["sample_id"] == "doe-j__all_documents__1"


def test_seed_is_reproducible(maildir: Path, tmp_path: Path):
    a = build_sample(maildir, tmp_path / "a", ["doe-j"], n=3, seed=7)
    b = build_sample(maildir, tmp_path / "b", ["doe-j"], n=3, seed=7)
    assert a["sampled"] == 3
    assert (tmp_path / "a" / "sample.csv").read_text() == (tmp_path / "b" / "sample.csv").read_text()


def test_refuses_to_overwrite(maildir: Path, tmp_path: Path):
    out = tmp_path / "out"
    build_sample(maildir, out, ["doe-j"])
    with pytest.raises(SampleExistsError):
        build_sample(maildir, out, ["doe-j"])
    build_sample(maildir, out, ["doe-j"], n=2, force=True)
    assert len(list((out / "texts").glob("*.txt"))) == 2  # stale texts cleared


def test_cli(maildir: Path, tmp_path: Path, capsys):
    out = tmp_path / "out"
    assert main(["sample", str(maildir), "--mailbox", "doe-j", "--out", str(out), "--n", "4"]) == 0
    assert json.loads(capsys.readouterr().out)["sampled"] == 4
    assert main(["sample", str(maildir), "--mailbox", "doe-j", "--out", str(out)]) == 1
