# deid-harness

A product-agnostic harness for measuring de-identification engines on real company email. Tonic Textual sits on the critical path; open-source engines (Presidio, seeded Faker, an own rebuild) plug in through the same adapter interface as comparison layers.

Status: Week 1 scaffold. Ingest manifest, response cache, and adapter interface are in place; labeling, scoring, and the Textual adapter come next.

## Layout

| Path | Purpose |
| --- | --- |
| `src/deid_harness/manifest.py` | Walks the Enron maildir and writes one row per message (hash, headers, recipient and word counts). The reconciliation baseline. |
| `src/deid_harness/cache.py` | Saves every engine response to disk, keyed by file hash plus engine name and config. Logs words sent on cache misses. |
| `src/deid_harness/engines/` | `Engine` base class, `CachedEngine` wrapper, and a `NullEngine` for zero-cost end-to-end runs. |
| `tests/` | pytest suite on synthetic fixture emails (invented people only). Runs in GitHub Actions. |

`data/` and `cache/` are git-ignored: raw email and engine output never go in the repo.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Get the Enron sample

Download the CMU release (about 420 MB compressed) from <https://www.cs.cmu.edu/~enron/> and extract it under `data/enron/`:

```bash
mkdir -p data/enron && cd data/enron
curl -LO https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
tar -xzf enron_mail_20150507.tar.gz   # creates data/enron/maildir/
cd ../..
```

## Build the manifest

Start small; the full corpus is about 500,000 messages.

```bash
deid manifest data/enron/maildir --mailbox allen-p --limit 500 --out data/manifest
```

Writes `data/manifest/manifest.csv` and `summary.json` (messages, bytes, body words, recipients, parse errors, duplicate hashes, counts per mailbox). The body word total is the budget figure to compare against Textual's 100,000-word free allowance.

## Track engine word usage

```bash
deid usage --cache cache --engine textual
```

## Adding an engine

Subclass `Engine`, set `name`, return settings that change output from `config()`, and map the tool's response to `EngineResult` (output text plus `Span(start, end, label, score)`). Wrap it in `CachedEngine` so every call checks the cache first.

## Notes

- Word counts are whitespace-based estimates; Tonic's own count may differ.
- The CMU release has attachments stripped, so `attachment_count` is usually 0.
- Built on personal time and equipment with public data only.
