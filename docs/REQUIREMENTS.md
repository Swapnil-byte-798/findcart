# FindCart: requirements and acceptance

## Product goal

Catalogue search that turns a shopping request into explicit, testable filters. A reviewer should be able to install the package, run its tests, inspect its SQL boundaries and exercise the core workflow without a custom frontend.

## Functional requirements

- Typed products, decimal prices and English/Hinglish rule-based filters
- Optional cached LLM filter parsing, plus lexical BM25 and character TF-IDF ranking
- Incremental updates, deletions, index rebuilds and atomic index activation
- Facets, autocomplete, deterministic pagination and a real derived UCI catalogue

## Acceptance conditions

1. Filtering cannot return a price or currency outside the parsed constraints.
2. A change or deletion must be visible after index synchronization.
3. Pagination cursors must reject a changed query or index version.
4. The application cannot invent a numeric budget from the word cheap.

## Quality requirements

Persist domain state transactionally; validate untrusted inputs; keep provider failures visible; avoid credential and prompt disclosure in diagnostic errors; provide an installable Python package, authenticated API, container and repeatable automated checks. Keep fixture evidence distinct from public-data and live-provider evidence.

## Scope boundary

Ranking is lexical and typo-tolerant, not neural embedding search. The included 3,898-product GBP catalogue is derived from historical UK transactions, not current inventory or prices. Missing brand/material/occasion attributes are not invented. Incremental indexing uses SQLite, not Kafka or OpenSearch. A small search run is functional evidence, not a relevance benchmark.

## Evaluation plan

Budget and currency filters, typo ranking, facets, deterministic cursors, cursor invalidation, atomic rebuilds, deletion sync and parsing validation. External checks need the credentials, model files or network access described in the runbook. Before publishing quality claims, create a labelled evaluation set and report sample size, metric definition, model version and measured failures. Build a labelled query/product judgement set and compare recall and ranking quality before adding neural retrieval.
