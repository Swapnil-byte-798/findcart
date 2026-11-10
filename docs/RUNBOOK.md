# FindCart: runbook

## Install and configure

Follow README.md with Python 3.11 or 3.12. Python 3.11 or 3.12. The committed catalogue contains product-level fields and omits customer identifiers.

Run `python -m findcart setup --shared` to enter reusable provider keys through hidden prompts, then `python -m findcart setup` to generate local operator tokens. A local nonempty key overrides the shared value. Leave optional keys empty. An existing local `.env` is deliberately not overwritten; edit it locally to rotate values. `PORTFOLIO_SECRETS_FILE` changes the shared-file location. Environment variables override both files.

No key for search, indexing or rule parsing. GROQ_API_KEY is optional for live=true query interpretation. Never send keys in chat, URLs, screenshots, issue comments, command arguments or Git. The repository's placeholders are intentionally blank.

## Operate

`python -m findcart check-keys` only reports which keys exist. `python -m findcart serve --port 8020` starts the loopback API. The health endpoint proves process availability, not provider availability. Use `/docs` to inspect request schemas. Operator endpoints use API_TOKEN; invoice review uses REVIEWER_TOKEN; scoped client/account/tenant endpoints use the token returned at creation.

Local state defaults to `.data/` under the current working directory. API state can be relocated with the DATA_DIR environment variable. Protect the entire directory and its backups. Restarting preserves committed data; do not delete the database to repair a failed request. Inspect the service's state or report endpoint and its domain tests first.

## Container

```bash
docker build -t findcart:local .
docker volume create findcart-data
docker run --rm --env-file .env -p 127.0.0.1:8020:8020 -v findcart-data:/data findcart:local
```

The image runs as a non-root user. If using a bind mount instead of the named volume, give that user write access. A shared credential file outside the container is not mounted automatically; supply required variables securely. QuietScribe also needs a read-only mount containing prepared model weights.

## Verify changes

Run `python -m pytest -q`, `python -m findcart demo` and `python -m pip wheel . --no-deps -w /tmp/wheels`. CI repeats unit/API checks on Python 3.11 and 3.12 and runs an installed wheel outside the checkout. No provider credentials are needed for normal CI.

Automated scope: Budget and currency filters, typo ranking, facets, deterministic cursors, cursor invalidation, atomic rebuilds, deletion sync and parsing validation.

Live acceptance remains a separate step: configure only the required provider, use a non-sensitive sample, exercise the real API path, and record model version, call count, usage, latency and any validation error. Do not substitute a demo response when a live request fails. Provider availability, pricing and limits can change independently of the code.

## Troubleshooting

- HTTP 401: verify token scope; provider keys are not application tokens.
- HTTP 409: inspect the original request/state and use the same payload when replaying a request key.
- HTTP 429: inspect the local quota and upstream limits; do not repeat blindly.
- HTTP 502/503: check configured providers, network access or required local models; errors deliberately omit upstream response bodies and credentials.
- SQLite lock errors: keep transactions short and use a single host with persistent storage; plan a database change before multiple replicas.

Ranking is lexical and typo-tolerant, not neural embedding search. The included 3,898-product GBP catalogue is derived from historical UK transactions, not current inventory or prices. Missing brand/material/occasion attributes are not invented. Incremental indexing uses SQLite, not Kafka or OpenSearch. A small search run is functional evidence, not a relevance benchmark.
