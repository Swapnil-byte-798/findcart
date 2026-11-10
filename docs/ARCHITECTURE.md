# FindCart: architecture

## Request and data path

Product changes → transactional outbox → active index → parsed query → lexical/typo ranking → facets and version-bound cursor

`api.py` validates transport input and credentials. `service.py` owns domain invariants and SQL transitions. `runtime.py` supplies small, vendored transport/configuration conventions so the repository can install independently. `cli.py` exposes setup, a labelled demo and serving commands. SQL schemas live beside the service that owns them.

## Decisions

Python and SQL keep the project aligned with the portfolio's existing skills. FastAPI supplies an inspectable contract without authored web code. SQLite provides a durable, low-cost local path; it is not a distributed database. The service owns transaction boundaries rather than spreading writes across API handlers. Domain services accept provider fixtures for tests; production commands never replace failed upstream calls with fixtures.

Provider keys come from owner-only files or the process environment. Tokens are distinct from provider keys. Never put a provider key into a public API client's configuration. Concurrent SQL writes are admitted transactionally; processes that die during external work can require operator recovery rather than unsafe automatic replay.

## Failure boundaries

1. Filtering cannot return a price or currency outside the parsed constraints.
2. A change or deletion must be visible after index synchronization.
3. Pagination cursors must reject a changed query or index version.
4. The application cannot invent a numeric budget from the word cheap.

Missing credentials return a configuration failure. Invalid provider structures fail validation. Network requests have timeouts and no silent retries through the common JSON client. An upstream timeout can still consume provider tokens; local rollback cannot undo external billing.

## Capacity and security limits

Ranking is lexical and typo-tolerant, not neural embedding search. The included 3,898-product GBP catalogue is derived from historical UK transactions, not current inventory or prices. Missing brand/material/occasion attributes are not invented. Incremental indexing uses SQLite, not Kafka or OpenSearch. A small search run is functional evidence, not a relevance benchmark.

Bind locally for development. Before external hosting, add TLS, gateway request-size limits, restricted egress, protected persistent storage, retention policies and a process-specific secret store. No internet-facing deployment or production security certification is claimed by this repository.
