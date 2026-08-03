# Tests

## Prerequisites

- **Neo4j connection**: Integration and API tests require a running Neo4j instance. Configure credentials via environment variables (`EDUCEDB_URI`, `EDUCEDB_USER`, `EDUCEDB_PASSWORD`) or `~/.educedb` config file. See the project CLAUDE.md for details.
- **REST API server**: API and client tests require a running FastAPI server (`uv run uvicorn educelab.hercdb.rest.server:app --reload`). Update `host_ip` and `token` in the test files as needed.

## Continuous Integration

These suites are **not run in CI**. Every test here requires live infrastructure —
a Neo4j instance populated with real HercDB data (and, for `api/`/`client/`, a running
REST server plus a valid token) — which a stock GitHub Actions runner does not have.
They are run locally against a real database as described below.

The GitHub Actions `CI` workflow (`.github/workflows/ci.yml`) instead runs a build +
import smoke test across Python 3.10–3.12, which guards packaging and the PyPI publish
path without needing a database.

## Test Suites

| Directory | Description | Requires |
|-----------|-------------|----------|
| `integration/` | Direct Neo4j database queries via `GraphDBConnection` | Neo4j |
| `api/` | REST API endpoint tests via `requests` | Neo4j + REST server |
| `client/` | `HercClient` wrapper tests against the REST API | Neo4j + REST server |

### integration/

- **test_db_queries.py** - Query methods: PHerc lookups, dataset queries, pipeline status, EduceLabID resolution (`unittest.TestCase` classes)
- **test_connection.py** - Basic Neo4j connection verification (plain script)
- **test_fuzzy_find_node.py** - `GraphDBConnection.fuzzy_find_node` tests (`unittest.TestCase`)
- **test_pipeline_crud.py** - Pipeline CRUD methods on `GraphDBConnection`: create/update/delete pipelines and processes (`unittest.TestCase`, self-cleaning)
- **test_pipeline_loader.py** - Pipeline/process node creation via `PhercGraphDatabaseLoader` (script with `--create`/`--cleanup` flags; run directly, not via `unittest`)

### api/

- **test_server.py** - REST API endpoint tests (script; pass `token` and optional `host_ip` on the command line)
- **test_fuzzy_endpoints.py** - Integration tests for the `/resolve` endpoint (script; `token` and optional `host_ip` args)
- **test_pipeline_endpoints.py** - Pipeline CRUD REST endpoint tests; seeds temporary PGSRaw/SpectralRaw input nodes and a live Neo4j connection in addition to the REST server (script; `token` and optional `host_ip` args)

### client/

- **test_herc_client.py** - `HercClient` dataset-finding methods (script — edit `token`/`host_ip` at the top)
- **test_client_retry.py** - Self-contained `unittest` module for `HercClient`'s automatic retry/timeout behavior; spins up a scripted local HTTP server, no live Neo4j/REST server needed
- **test_lcc_workflow.py** - LCC workflow walkthrough via `HercClient` (script — edit `token`/`host_ip` at the top)
- **test_pipeline_client.py** - `HercClient` pipeline CRUD methods (script — edit `token`/`host_ip` at the top)
- **test_resolve_client.py** - `HercClient.resolve` tests (script — edit `token`/`host_ip` at the top)

## Running Tests

```bash
# All tests
uv run python -m unittest discover tests

# A specific test directory
uv run python -m unittest discover tests/integration

# A specific test file
uv run python -m unittest tests/integration/test_db_queries.py

# A specific test class
uv run python -m unittest tests.integration.test_db_queries.TestPhercDbQueries

# A specific test method
uv run python -m unittest tests.integration.test_db_queries.TestPhercDbQueries.test_find_artifact_name_by_uuid

# test_client_retry.py is self-contained (no live server needed)
uv run python -m unittest tests.client.test_client_retry
```

Note: most `api/` and `client/` test files are scripts rather than `unittest.TestCase` classes (`test_client_retry.py` is the exception) — run them directly, passing a token and host as needed:

```bash
uv run python tests/api/test_server.py <token> [host_ip]
uv run python tests/client/test_herc_client.py   # edit token/host_ip at the top of the file first
```
