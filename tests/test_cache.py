from deid_harness.cache import ResponseCache, cache_key
from deid_harness.engines import CachedEngine, Engine, EngineResult, NullEngine, Span


class CountingEngine(Engine):
    name = "counting"

    def __init__(self, mode: str = "redact") -> None:
        self.mode = mode
        self.calls = 0

    def config(self):
        return {"mode": self.mode}

    def process(self, text):
        self.calls += 1
        return EngineResult(output_text="[NAME] hi", spans=[Span(0, 4, "NAME_GIVEN", 0.9)])


def test_second_call_hits_cache(tmp_path):
    engine = CountingEngine()
    cached = CachedEngine(engine, ResponseCache(tmp_path))
    first = cached.run(b"Jane hi", "Jane hi")
    second = cached.run(b"Jane hi", "Jane hi")
    assert engine.calls == 1
    assert (cached.hits, cached.misses) == (1, 1)
    assert second.spans == first.spans == [Span(0, 4, "NAME_GIVEN", 0.9)]


def test_config_change_is_a_new_key(tmp_path):
    cache = ResponseCache(tmp_path)
    CachedEngine(CountingEngine("redact"), cache).run(b"x", "x")
    synth = CountingEngine("synthesize")
    CachedEngine(synth, cache).run(b"x", "x")
    assert synth.calls == 1
    assert cache_key("e", {"a": 1, "b": 2}, "h") == cache_key("e", {"b": 2, "a": 1}, "h")


def test_usage_ledger_counts_only_misses(tmp_path):
    cache = ResponseCache(tmp_path)
    cached = CachedEngine(CountingEngine(), cache)
    cached.run(b"one two three", "one two three")
    cached.run(b"one two three", "one two three")
    cached.run(b"four five", "four five")
    assert cache.words_used() == 5
    assert cache.words_used("counting") == 5
    assert cache.words_used("other") == 0


def test_null_engine_round_trip(tmp_path):
    text = "Call Maria at 713-555-0142."
    result = CachedEngine(NullEngine(), ResponseCache(tmp_path)).run(text.encode(), text)
    assert result.output_text == text and result.spans == []
