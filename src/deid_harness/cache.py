"""Disk cache for engine responses.

Every engine response is saved as JSON, keyed by the input file's hash plus the
engine's name and configuration. Changing the engine config produces a new key,
so a settings change never returns a stale answer. The cache is checked before
any API call; a miss is recorded in a usage ledger so paid words can be tracked
against the free allowance.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .textutil import sha256_bytes


def config_fingerprint(config: dict[str, Any]) -> str:
    """Stable hash of an engine config (key order does not matter)."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def cache_key(engine_name: str, config: dict[str, Any], file_hash: str) -> str:
    material = f"{engine_name}\n{config_fingerprint(config)}\n{file_hash}"
    return sha256_bytes(material.encode("utf-8"))


@dataclass
class CacheHit:
    key: str
    response: dict[str, Any]


class ResponseCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.ledger_path = self.root / "usage.jsonl"

    def _path(self, engine_name: str, key: str) -> Path:
        return self.root / engine_name / key[:2] / f"{key}.json"

    def get(self, engine_name: str, key: str) -> CacheHit | None:
        path = self._path(engine_name, key)
        if not path.exists():
            return None
        return CacheHit(key=key, response=json.loads(path.read_text(encoding="utf-8")))

    def put(self, engine_name: str, key: str, response: dict[str, Any]) -> Path:
        path = self._path(engine_name, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # atomic on the same filesystem
        return path

    def record_usage(self, engine_name: str, file_hash: str, words: int) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.time(), "engine": engine_name, "file_hash": file_hash, "words": words}
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def words_used(self, engine_name: str | None = None) -> int:
        """Total words sent to engines on cache misses (optionally one engine)."""
        if not self.ledger_path.exists():
            return 0
        total = 0
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if engine_name is None or entry["engine"] == engine_name:
                total += int(entry["words"])
        return total
