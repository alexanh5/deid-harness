"""Engine adapter interface.

Each de-identification tool (Tonic Textual, Presidio, your own code) plugs in
through a small adapter that returns the same shape: detected spans plus the
transformed text. The harness scores every engine against the same labels.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from ..cache import ResponseCache, cache_key
from ..textutil import sha256_bytes, word_count


@dataclass(frozen=True)
class Span:
    start: int  # character offset, inclusive
    end: int  # character offset, exclusive
    label: str  # entity type, e.g. NAME_GIVEN, EMAIL_ADDRESS
    score: float | None = None


@dataclass
class EngineResult:
    output_text: str
    spans: list[Span] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)  # engine's own response, for audit

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_text": self.output_text,
            "spans": [asdict(s) for s in self.spans],
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EngineResult":
        return cls(
            output_text=data["output_text"],
            spans=[Span(**s) for s in data.get("spans", [])],
            raw=data.get("raw", {}),
        )


class Engine(ABC):
    """Subclass per tool. Keep adapters thin: call the tool, map its output."""

    name: str = "engine"

    def config(self) -> dict[str, Any]:
        """Settings that change output. Part of the cache key."""
        return {}

    @abstractmethod
    def process(self, text: str) -> EngineResult: ...


class CachedEngine:
    """Wraps an engine so every call checks the disk cache first."""

    def __init__(self, engine: Engine, cache: ResponseCache) -> None:
        self.engine = engine
        self.cache = cache
        self.hits = 0
        self.misses = 0

    def run(self, raw_bytes: bytes, text: str) -> EngineResult:
        file_hash = sha256_bytes(raw_bytes)
        key = cache_key(self.engine.name, self.engine.config(), file_hash)
        hit = self.cache.get(self.engine.name, key)
        if hit is not None:
            self.hits += 1
            return EngineResult.from_dict(hit.response)
        result = self.engine.process(text)
        self.cache.put(self.engine.name, key, result.to_dict())
        self.cache.record_usage(self.engine.name, file_hash, word_count(text))
        self.misses += 1
        return result
