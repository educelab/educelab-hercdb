# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **educelab-hercdb**, a Python package providing a graph database API and REST API for managing Herculaneum papyrus scroll data. The database uses Neo4j to model relationships between papyrus fragments (PHerc), their physical subdivisions (Cornice, Pezzo), metadata, imaging datasets, and processing pipelines.

## Development Commands

### Environment Setup
```bash
# This project uses uv for dependency management
# Install dependencies and create virtual environment
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On macOS/Linux
```

### Testing
```bash
# Run all tests
uv run python -m unittest discover tests

# Run integration tests (requires Neo4j connection)
uv run python -m unittest discover tests/integration

# Run a specific test file
uv run python -m unittest tests/integration/test_db_queries.py

# Run a specific test class or method
uv run python -m unittest tests.integration.test_db_queries.TestPhercDbQueries
uv run python -m unittest tests.integration.test_db_queries.TestPhercDbQueries.test_find_pherc_by_uuid

# Run test scripts directly
uv run tests/integration/test_pipeline_loader.py
```

### Running the REST API Server
```bash
# Start the FastAPI server
uv run uvicorn educelab.hercdb.rest.server:app --reload
```

### Database Configuration

The package reads Neo4j connection settings from:
1. Environment variables (highest priority): `EDUCEDB_URI`, `EDUCEDB_USER`, `EDUCEDB_PASSWORD`
2. Config file at `~/.educedb` (TOML format)
3. Interactive prompt via `hercdb.config.request_required()`

Example `~/.educedb`:
```toml
[database]
uri = "neo4j://localhost:7687"
username = "neo4j"
password = "your_password"
```

## Architecture

### Project Structure

```
educelab-hercdb/
├── src/educelab/hercdb/
│   ├── __init__.py           # Package exports (backward-compatible)
│   ├── config.py             # Configuration management
│   │
│   ├── db/                   # Database layer
│   │   ├── __init__.py       # Exports GraphDBConnection, connect(), DatasetType
│   │   └── connection.py     # GraphDBConnection class and queries
│   │
│   ├── rest/                 # REST API layer
│   │   ├── __init__.py
│   │   ├── server.py         # FastAPI app and routes
│   │   └── README.md
│   │
│   ├── client/               # REST API Python client
│   │   ├── __init__.py       # Exports HercClient
│   │   ├── herc_client.py    # HercClient class
│   │   └── README.md
│   │
│   ├── loader/               # Data loading utilities
│   │   ├── __init__.py       # Exports PhercGraphDatabaseLoader
│   │   ├── graph_loader.py   # PhercGraphDatabaseLoader class
│   │   ├── metadata_loader.py
│   │   └── scan_loader.py
│   │
│   └── cli/                  # Command-line tools
│       ├── __init__.py
│       └── search.py
│
├── old_scripts/              # Legacy experimental scripts, not currently in use
├── preprocessing/            # Data preparation (notebooks, etc.)
├── tests/
│   ├── integration/          # Tests requiring Neo4j
│   ├── api/                  # REST API tests
│   └── client/               # REST API client tests
└── input_data/
```

### Core Components

**src/educelab/hercdb/db/connection.py**: Main database interface
- `GraphDBConnection`: Primary class for Neo4j interactions
- `connect()`: Factory function that uses config to create connections
- Contains all query methods for finding and filtering PHerc nodes
- Key enums: `DatasetType` (FlatbedScan, PGSRaw, SpectralRaw)

**src/educelab/hercdb/config.py**: Configuration management
- Loads settings from environment variables, `~/.educedb` file, or prompts
- Uses `tomllib` (Python 3.11+) or `configparser` (Python 3.10)

**src/educelab/hercdb/rest/server.py**: FastAPI REST API
- Token-based authentication using `~/.tokens` file
- Endpoints for querying PHerc, Cornice, Pezzo nodes and their relationships
- `/search` endpoint supports complex multi-parameter queries

**src/educelab/hercdb/loader/graph_loader.py**: Database loading utilities
- `PhercGraphDatabaseLoader`: Class for bulk data loading operations
- Used by scripts in `old_scripts/` directory to populate the database

**src/educelab/hercdb/client/herc_client.py**: REST API client
- `HercClient`: Lightweight Python client wrapping all REST endpoints
- Constructor takes `host`, `token`, and optional `port` and `scheme`
- Methods mirror REST endpoints (`get_pherc`, `get_subdivisions`, `search`, `get_pipelines`, etc.)

### Import Patterns

```python
# Recommended new imports
from educelab.hercdb.db import connect, GraphDBConnection, DatasetType
from educelab.hercdb.loader import PhercGraphDatabaseLoader
from educelab.hercdb.client import HercClient

# Backward-compatible imports (still work)
from educelab.hercdb import connect, GraphDBConnection
from educelab.hercdb.api import DatasetType  # via alias
```

### Graph Database Schema

The Neo4j database models Herculaneum scroll data with these primary node types:

- **PHerc**: Individual papyrus scrolls (identified by `displayName`)
- **Cornice**: Physical subdivisions of PHerc (some scrolls)
- **Pezzo**: Smaller fragments (can be under PHerc or Cornice)
- **Disegni**: Historical drawings depicting scrolls
- **EduceLabID**: Links physical objects to UUIDs and datasets
- **Dataset nodes**: FlatbedScanDataset, PGSRaw, SpectralRaw (imaging data)
- **Pipeline**: Processing pipelines with `pipeline_id`
- **Process**: Pipeline stages with `stage`, `status`, `datetime`, `slurm_id`
- **Metadata nodes**: Author, Language, Unroller, CustodialInstitution, etc.

Key relationships:
- `PHerc -[:HAS]-> Cornice -[:HAS]-> Pezzo`
- `PHerc -[:HAS]-> Pezzo` (direct)
- `EduceLabID -[:ASSIGNED_TO]-> (PHerc|Cornice|Pezzo)`
- `Dataset -[:BELONGS_TO]-> EduceLabID`
- `Process -[:STAGE_OF]-> Pipeline`
- `PHerc -[:AUTHORED_BY]-> Author`, `PHerc -[:HAS_LANGUAGE]-> Language`, etc.

### API Query Patterns

The `GraphDBConnection` class provides two patterns for queries:

1. **Specific lookups** (return records, summary, keys):
   - `find_pherc_by_uuid()`, `find_pherc_by_display_name()`
   - `find_pherc_by_author()`, `find_pherc_by_language()`
   - `find_pherc_by_property_value()` (case-insensitive partial match)
   - `find_pherc_by_numeric_property()` (diameter, height, width, weight)

2. **Dataset queries**:
   - `find_datasets(ds_type, pherc, cornice=None, pezzo=None, newest_completed=False, properties_only=True)`
   - `find_datasets_for_educelabid(uuid, ds_type=None, newest_completed=False)` - datasets for a specific EduceLabID
   - `find_all_datasets_for_pherc(pherc_display_name, ds_type=None, newest_completed=False)` - all datasets grouped by EduceLabID
   - `find_educelabids_for_pherc(pherc_display_name)` - list all EduceLabIDs under a PHerc

3. **Node traversal**:
   - `get_directly_attached_nodes()` - gets all nodes connected to a given node
   - `list_cornici_pezzi(pherc)` / `list_cornici_and_pezzi_for_pherc(pherc_display_name)` - full hierarchy of Cornici and Pezzi
   - `records_to_label_json()` - static method to convert Neo4j records to JSON

4. **UUID lookups**:
   - `find_artifact_name_by_uuid(uuid)` - returns dict with `pherc`, `cornice`, `pezzo` display names for a UUID

5. **Pipeline queries**:
   - `find_pipelines()` - returns list of all pipelines with their `pipeline_id` and `artifact_uuid`
   - `get_pipeline_status(pipeline_id)` - returns list of process stages with `datetime`, `stage`, `status`, `slurm_id`
   - `get_all_pipeline_summaries()` - returns all pipelines with aggregated status info

6. **Pipeline CRUD**:
   - `initialize_pipeline(pipeline_id, artifact_uuid, datetime)` - create a Pipeline node linked to an EduceLabID
   - `initialize_process(pipeline_id, proc_type, input_dataset_paths, output_dataset_path, slurm_id, start_datetime)` - create a Process node (PGS, SPEC, REG, WEB) with input/output dataset links
   - `update_process_status(pipeline_id, stage, status, end_datetime)` - update process status to completed or failed
   - `delete_pipeline(pipeline_id)` - delete a Pipeline, all its Process nodes, and output dataset nodes (leaves input datasets untouched)
   - `get_pipeline_confirmation(pipeline_id)` - full pipeline summary with all stages

### REST API Endpoints

Protected by Bearer token authentication (tokens in `~/.tokens`):

- `GET /check-token` - Verify token validity
- `GET /pherc/{pherc_id}` - Get PHerc and all attached nodes
- `GET /pherc/{pherc_id}/cornice/{cornice_id}` - Get specific Cornice
- `GET /pherc/{pherc_id}/pezzo/{pezzo_id}` - Get Pezzo directly under PHerc
- `GET /pherc/{pherc_id}/cornice/{cornice_id}/pezzo/{pezzo_id}` - Get Pezzo under Cornice
- `GET /pherc/{pherc_id}/subdivisions` - List all Cornici and Pezzi (full hierarchy traversal)
- `GET /pherc/{pherc_id}/datasets/{dataset_type}` - Get imaging datasets with optional filtering
- `GET /pherc/{pherc_id}/all-datasets` - Get all datasets grouped by EduceLabID
- `GET /pherc/{pherc_id}/educelabids` - List all EduceLabIDs under PHerc
- `GET /artifacts/{uuid}` - Get display name for an artifact by UUID
- `GET /educelabid/{uuid}/datasets` - Get datasets for specific EduceLabID
- `POST /search` - Complex search with multiple parameters (supports intersection of multiple criteria)
- `GET /pipelines` - Get all pipelines with status summaries
- `GET /pipelines/{pipeline_id}/stages` - Get all process stages for a pipeline
- `POST /pipelines` - Create a new pipeline linked to an EduceLabID
- `POST /pipelines/{pipeline_id}/processes` - Create a new process (stage) within a pipeline
- `PUT /pipelines/{pipeline_id}/processes/{proc_type}/status` - Update process status
- `DELETE /pipelines/{pipeline_id}` - Delete a pipeline and all its processes and output datasets
- `GET /pipelines/{pipeline_id}/confirmation` - Get full pipeline summary with all stages

**Note:** The REST API renames the `stage` field to `proc_type` in pipeline stage responses to avoid ambiguity with pipeline stage ordering.

## Important Notes

### Display Names vs Internal Names
- Use `displayName` property for user-facing queries (e.g., "421", "118a")
- Older `name` and `human_name` properties are deprecated
- Methods marked "Soon to be deprecated" should be avoided in new code

### Naming Inconsistency: `stage` (Neo4j) vs `proc_type` (Python/REST)
- The Python API and REST layer use `proc_type` as the parameter/field name for process types (PGS, SPEC, REG, WEB).
- However, the Neo4j `Process` nodes still store this value under the property name `stage` in Cypher queries (e.g., `{stage: "PGS"}`).
- This mismatch should be reviewed and potentially reconciled in a future update.

### Query Methods
- Most find methods perform case-insensitive partial matching using Cypher regex: `(?i).*{value}.*`
- Results are typically ordered by `ph.displayName`
- `find_pherc_by_unrolled_year()` handles complex date formats like "1420, 1820-1858"

### Python Version Support
- Minimum: Python 3.10
- Config loading differs between 3.10 (configparser) and 3.11+ (tomllib)

### Data Loading
- Scripts in `old_scripts/` directory load data into Neo4j
- `educelab.hercdb.loader` module contains utilities for bulk operations
- `preprocessing/` has Jupyter notebooks for data preparation from Google Sheets

## Claude Code Instructions

### Planning Mode
When in planning mode, write the proposed plan to an `.md` file under `./.claude/` for review before implementation. The `.claude/` directory is gitignored and used for Claude-generated plans and drafts.
