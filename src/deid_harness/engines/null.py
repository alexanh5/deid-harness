"""Null engine: returns text unchanged and detects nothing.

Used to test the pipeline end to end at zero cost, and as the baseline for the
null-transform round trip (output must hash-match input).
"""

from __future__ import annotations

from .base import Engine, EngineResult


class NullEngine(Engine):
    name = "null"

    def process(self, text: str) -> EngineResult:
        return EngineResult(output_text=text, spans=[])
