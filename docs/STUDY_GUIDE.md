# FindCart: study guide

## Explain the problem

Catalogue search that turns a shopping request into explicit, testable filters. Explain who uses the workflow and why each confirmation, isolation or validation boundary exists before describing libraries.

## Read the implementation

1. Read `service.py` and its SQL schema. Name the durable entities and draw their valid state transitions.
2. Trace one successful API request from its Pydantic input to its committed writes.
3. Trace a provider failure and identify what can and cannot be rolled back.
4. Read the tests that enforce the acceptance conditions below. Explain why each failure would matter to a user.

1. Filtering cannot return a price or currency outside the parsed constraints.
2. A change or deletion must be visible after index synchronization.
3. Pagination cursors must reject a changed query or index version.
4. The application cannot invent a numeric budget from the word cheap.

## Interview discussion

- Where is the transaction boundary, and what happens if the process dies immediately after it?
- How are retries bound to the original request? Which operation can safely repeat?
- Which inputs are untrusted, and how are externally generated fields validated?
- What is tested with fixtures, what was measured on public data, and what remains unmeasured?
- What would change with ten times the data, multiple workers, or another tenant?

## Honest project explanation

Describe the implemented behavior, then demonstrate a representative test and explain its failure condition. Do not present mock latency, authored examples, uncalibrated scores or optional integrations as measured production results.

Known boundaries: Ranking is lexical and typo-tolerant, not neural embedding search. The included 3,898-product GBP catalogue is derived from historical UK transactions, not current inventory or prices. Missing brand/material/occasion attributes are not invented. Incremental indexing uses SQLite, not Kafka or OpenSearch. A small search run is functional evidence, not a relevance benchmark.

## Practical extension

Build a labelled query/product judgement set and compare recall and ranking quality before adding neural retrieval. Define a measurable acceptance criterion before extending the implementation.
