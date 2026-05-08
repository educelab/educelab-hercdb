# Tests

## Prerequisites

- **Neo4j connection**: Integration and API tests require a running Neo4j instance. Configure credentials via environment variables (`EDUCEDB_URI`, `EDUCEDB_USER`, `EDUCEDB_PASSWORD`) or `~/.educedb` config file. See the project CLAUDE.md for details.
- **REST API server**: API and client tests require a running FastAPI server (`uv run uvicorn educelab.hercdb.rest.server:app --reload`). Update `host_ip` and `token` in the test files as needed.

## Test Suites

| Directory | Description | Requires |
|-----------|-------------|----------|
| `integration/` | Direct Neo4j database queries via `GraphDBConnection` | Neo4j |
| `api/` | REST API endpoint tests via `requests` | Neo4j + REST server |
| `client/` | `HercClient` wrapper tests against the REST API | Neo4j + REST server |

### integration/

- **test_db_queries.py** - Query methods: PHerc lookups, dataset queries, pipeline status, EduceLabID resolution
- **test_connection.py** - Basic Neo4j connection verification
- **test_pipeline_loader.py** - Pipeline/process node creation via `PhercGraphDatabaseLoader`

### api/

- **test_server.py** - REST API endpoint tests (template — fill in `host_ip` and `token`)
- **test_server_local.py** - Same tests configured for localhost

### client/

- **test_herc_client.py** - `HercClient` tests (template — fill in `host_ip` and `token`)
- **test_herc_client_local.py** - Same tests configured for localhost

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
uv run python -m unittest tests.integration.test_db_queries.TestPhercDbQueries.test_find_pherc_by_uuid
```

Note: `api/` and `client/` test files are scripts rather than standard `unittest.TestCase` classes — run them directly:

```bash
uv run python tests/api/test_server_local.py
uv run python tests/client/test_herc_client_local.py
```
