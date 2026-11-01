"""Small text helpers shared by the manifest and the cache ledger."""

from __future__ import annotations

import hashlib
import re

_WORD_RE = re.compile(r"\S+")


def word_count(text: str) -> int:
    """Whitespace-delimited word count.

    This is an estimate for budgeting against Textual's word allowance.
    Tonic's own count may differ; record their figure when it is known.
    """
    return len(_WORD_RE.findall(text))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
