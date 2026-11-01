import csv
from pathlib import Path

from deid_harness.manifest import build_manifest, iter_message_files

FIXTURES = Path(__file__).parent / "fixtures" / "maildir"


def test_natural_order():
    names = [p.relative_to(FIXTURES).as_posix() for p in iter_message_files(FIXTURES)]
    assert names == [
        "doe-j/inbox/1.",
        "doe-j/inbox/2.",
        "doe-j/inbox/10.",
        "doe-j/sent_items/1.",
        "roe-m/inbox/1.",
    ]


def test_manifest_counts(tmp_path):
    summary = build_manifest(FIXTURES, tmp_path)
    assert summary["messages"] == 5
    assert summary["parse_errors"] == 0
    assert summary["by_mailbox"] == {"doe-j": 4, "roe-m": 1}
    # 3 recipients on msg 1, then 1, 2 (To + Bcc), 1, 1
    assert summary["recipients"] == 8

    rows = list(csv.DictReader((tmp_path / "manifest.csv").open(encoding="utf-8")))
    assert len(rows) == summary["messages"]
    first = rows[0]
    assert first["to_count"] == "2" and first["cc_count"] == "1"
    assert first["subject"] == "Q2 forecast review"
    assert int(first["body_words"]) == 20  # 11 + 8 + 1 words on three lines
    assert sum(int(r["body_words"]) for r in rows) == summary["body_words"]


def test_mailbox_filter_and_limit(tmp_path):
    assert build_manifest(FIXTURES, tmp_path, mailboxes=["roe-m"])["messages"] == 1
    assert build_manifest(FIXTURES, tmp_path, limit=2)["messages"] == 2
