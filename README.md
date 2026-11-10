# FindCart

Catalogue search that turns a shopping request into explicit, testable filters.

[![Python verification](https://github.com/Swapnil-byte-798/findcart/actions/workflows/ci.yml/badge.svg)](https://github.com/Swapnil-byte-798/findcart/actions/workflows/ci.yml)

Project 11 in a Python and SQL AI engineering portfolio. The interface is a Python CLI and FastAPI's generated API documentation.

## What works

- Typed products, decimal prices and English/Hinglish rule-based filters
- Optional cached LLM filter parsing, plus lexical BM25 and character TF-IDF ranking
- Incremental updates, deletions, index rebuilds and atomic index activation
- Facets, autocomplete, deterministic pagination and a real derived UCI catalogue

## Run it

Python 3.11 or 3.12. The committed catalogue contains product-level fields and omits customer identifiers.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest -q
python -m findcart demo
python -m findcart setup
python -m findcart serve --port 8020
```

Open http://127.0.0.1:8020/docs. `setup` prompts for credentials without displaying them, generates independent operator/reviewer tokens, and stores them in an ignored file with owner-only permissions. Use the operator token as `Authorization: Bearer ...`; account, client and tenant endpoints issue their own scoped tokens. Do not commit any of these values.

The demo is explicitly labelled: authored fixtures exercise the workflow, not a live provider. `check-keys` reports configuration only and never claims a provider has been validated.

## Credentials

No key for search, indexing or rule parsing. GROQ_API_KEY is optional for live=true query interpretation.

To reuse a provider key across these repositories, run `python -m findcart setup --shared` before the local `setup` command. The shared prompt adds missing keys and preserves existing nonempty keys. Local environment variables take precedence. See [.env.example](.env.example) for names only; real keys are never shipped.

## Design and boundaries

Product changes → transactional outbox → active index → parsed query → lexical/typo ranking → facets and version-bound cursor

Ranking is lexical and typo-tolerant, not neural embedding search. The included 3,898-product GBP catalogue is derived from historical UK transactions, not current inventory or prices. Missing brand/material/occasion attributes are not invented. Incremental indexing uses SQLite, not Kafka or OpenSearch. A small search run is functional evidence, not a relevance benchmark.

## Verification

Budget and currency filters, typo ranking, facets, deterministic cursors, cursor invalidation, atomic rebuilds, deletion sync and parsing validation. Common tests also cover hidden setup, configuration precedence, provider response validation, API authentication and transactional rollback.

[Verification record](evidence/verification.json) separates automated checks from provider-dependent acceptance. No result represents all possible inputs, production load, or a calibrated model-quality benchmark.

## Read further

- [Requirements and acceptance](docs/REQUIREMENTS.md)
- [Architecture and decisions](docs/ARCHITECTURE.md)
- [Runbook and key setup](docs/RUNBOOK.md)
- [Study guide](docs/STUDY_GUIDE.md)

## Next engineering milestone

Build a labelled query/product judgement set and compare recall and ranking quality before adding neural retrieval.
