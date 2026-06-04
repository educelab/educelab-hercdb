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
# Start the FastAPI server (development, with auto-reload)
uv run uvicorn educelab.hercdb.rest.server:app --reload
```

### Admin CLI tools

After `uv sync --extra server`, the package exposes shell entry points (see `[project.scripts]` in `pyproject.toml`):

- `el-hercdb-search` — interactive PHerc lookup (`cli/search.py`)
- `el-hercdb-scan-report` — scan-completeness CSV report (`cli/scan_completeness.py`); writes a full report and an issues-only report, walking the PHerc hierarchy plus any `REPLACES` chains. Run via `uv run el-hercdb-scan-report --out-dir ./tmp`.

### Deploying the REST API Server (Production)

For full server setup (Neo4j credentials, API tokens, systemd service), see `docs/SERVER_SETUP.md`. For a visual overview, see `docs/hercdb_setup_quickstart.svg`.

### Database Configuration

The package reads Neo4j connection settings from:
1. Environment variables (highest priority): `EDUCEDB_URI`, `EDUCEDB_USER`, `EDUCEDB_PASSWORD`
2. Config file at `~/.educedb` (TOML format)
3. Interactive prompt via `hercdb.config.request_required()`

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
│   │   ├── hercdb.service    # systemd service file for production deployment
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
│       ├── search.py
│       └── scan_completeness.py
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
- `fuzzy_find_node(name, label, parent_pherc, parent_cornice, threshold, limit)`: standalone reusable primitive for fuzzy-resolving noisy PHerc/Cornice/Pezzo displayNames to ranked candidates; see "Fuzzy name lookup" under API Query Patterns
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
- `mark_educelabid_retired(uuid, reason)` sets `retired = true` and stores a reason string on an EduceLabID; called by `metadata_loader.py` when a Replacement UUID is a sentinel like `"discarded"` or `"."` rather than a real UUID

**src/educelab/hercdb/loader/scan_loader.py**: Scan-data loader
- Loads the 2026 scan schema: PGS and Spectral CSVs both carry `file count, missing files, zero-byte files, short files, bad format files` (parsed as ints onto the nodes as `file_count, missing_files, zero_byte_files, short_files, bad_format_files`). The Spectral `sample uuid 2` column was dropped in 2026; the loader no longer reads it.
- `normalize_complete(raw)` collapses CSV `complete` variants (`"TRUE"` / `"True"` / `"true"` / etc.) to the canonical strings `"True"`, `"False"`, or `"unknown"` so PGS and Spectral nodes share the same `complete` semantics. The canonical strings always satisfy the loader's `if complete:` guard, so re-runs overwrite stale values in either direction.
- `--replace` (default on; `--no-replace` to disable) calls `loader.delete_all_scan_nodes()` to DETACH DELETE all PGSRaw/SpectralRaw nodes before reloading (FlatbedScanDataset untouched). `add_pgs_raw_node` / `add_spectral_raw_node` MERGE on the scan `uuid` alone (a unique key) and SET `path`/`date_start`/counts, so a changed path updates the node in place rather than duplicating it — the load is idempotent.
- The 2023 → 2026 reconciliation that produced the spectral ground-truth file (`input_data/spectral_datasets_20260601_reconciled.csv`) is recorded in `docs/data_review_notes.md` §5 (78 backfilled sample uuids, 147 unlinked calibration/test scans, 1 dropped `sample uuid 2`).

**src/educelab/hercdb/cli/scan_completeness.py**: Scan-completeness report CLI
- Generates `scan_completeness_full.csv` and `scan_completeness_issues.csv`
- Wired up as the `el-hercdb-scan-report` shell command via `[project.scripts]`
- Walks `REPLACES` so pre-replacement scans on retired predecessor UUIDs still count toward an artifact's coverage
- A dataset counts as **complete** only when `complete == "True"` AND `missing_files == 0 AND zero_byte_files == 0 AND short_files == 0 AND bad_format_files == 0` (see `_is_fully_complete`). This is stricter than the raw `complete` flag and is local to this report — `find_datasets` / `find_datasets_for_educelabid` / `find_all_datasets_for_pherc` still filter on the raw flag Cypher-side and need reconciling (tracked in memory).

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

- **PHerc**: Individual papyrus scrolls (identified by `displayName`). PHercs that are organized as Casette also carry the additional `:Casetta` label.
- **Cornice**: Physical subdivisions of PHerc (some scrolls)
- **Pezzo**: Smaller fragments (can be under PHerc or Cornice)
- **Disegni**: Historical drawings depicting scrolls
- **EduceLabID**: Links physical objects to UUIDs and datasets. May carry a `retired = true` flag with a `retired_reason` string when the UUID was retired without a successor (sentinel `Replacement UUID` value in the UUID file).
- **Dataset nodes**: FlatbedScanDataset, PGSRaw, SpectralRaw (imaging data). PGSRaw/SpectralRaw carry `uuid` (the scan's own id, the MERGE key), `path`, `date_start`/`date_end`, `complete`, and the 2026 integer counts `file_count`, `missing_files`, `zero_byte_files`, `short_files`, `bad_format_files`.
- **Pipeline**: Processing pipelines with `pipeline_id`
- **Process**: Pipeline stages with `stage`, `status`, `datetime`, `slurm_id`
- **Metadata nodes**: Author, Language, Unroller, CustodialInstitution, etc.

Key relationships:
- `PHerc -[:HAS]-> Cornice -[:HAS]-> Pezzo`
- `PHerc -[:HAS]-> Pezzo` (direct)
- `EduceLabID -[:ASSIGNED_TO]-> (PHerc|Cornice|Pezzo)`
- `Dataset -[:BELONGS_TO]-> EduceLabID`
- `(new:EduceLabID) -[:REPLACES]-> (orig:EduceLabID)` — UUID replacement chain. Only the new UUID gets `ASSIGNED_TO` an artifact; pre-replacement scans may still `BELONG_TO` the original. Walk `[:REPLACES*0..]` from the active UUID to gather scans across the chain.
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
   - `find_datasets_for_educelabid(uuid, ds_type=None, newest_completed=False)` - datasets for a specific EduceLabID (single-UUID view used by the REST endpoint)
   - `find_datasets_for_educelabid_with_predecessors(uuid, ds_type=None)` - same shape, but walks `[:REPLACES*0..]` from the given UUID so pre-replacement scans on retired predecessor UUIDs are pooled in. Used by the scan-completeness report; do not use for REST responses unless you intend to include the full chain.
   - `find_all_datasets_for_pherc(pherc_display_name, ds_type=None, newest_completed=False)` - all datasets grouped by EduceLabID
   - `find_educelabids_for_pherc(pherc_display_name)` - list all EduceLabIDs under a PHerc (UUIDs-only view; drops artifacts without UUIDs)
   - `find_all_artifacts_and_educelabids_for_pherc(pherc_display_name)` - one record per (artifact, UUID) pair, plus a sentinel record for any artifact with no UUID. Suppresses the PHerc-itself row when the PHerc has Cornici/Pezzi children but no direct UUID. Used by the scan-completeness report.

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

7. **Fuzzy name lookup** (`src/educelab/hercdb/db/connection.py`):
   - `fuzzy_find_node(name, label="PHerc", parent_pherc=None, parent_cornice=None, threshold=75, limit=10)` — standalone reusable primitive that returns ranked candidates: `[{"node", "displayName", "score", "parent_pherc", "parent_cornice"}, ...]` ordered by score desc. Use this when callers have a noisy name (typos, extra spaces, alternate spellings) and need to identify the right PHerc/Cornice/Pezzo before reaching for UUIDs/EduceLabIDs and the other `find_*` methods. **Do not** add per-endpoint fuzzy variants — compose with this method.
   - Implementation notes: normalizes by stripping **all** whitespace + lowercasing both query and candidate before scoring; exact match after normalization short-circuits to score 100 (all candidates sharing the normalized name are returned). Uses `rapidfuzz.fuzz.ratio` (not `WRatio`) — `ratio` penalizes length mismatch, which works correctly for the mostly-short identifier-style displayNames in this dataset; `WRatio`'s partial-ratio component over-scored short substrings of the query. Among equal-score candidates, substring matches (query appears verbatim in the candidate's normalized name) sort before non-substring matches — e.g. "118a"/"1180" rank above "1168" for query "118", and "Cass."/"Cassetta" rank above unrelated names for query "cass". Alphanumeric suffix names like "118a" still require `limit ≥ 13` to appear when there are many numeric substring matches ("1118", "1180"–"1189") sorting before them alphabetically.
   - Parent semantics: for `Cornice`/`Pezzo`, the resolver recursively fuzzy-resolves any supplied parent name and scopes the child candidate fetch to those parents. Parent scores are reported separately on each result (not fused with the child score). When a parent name was *not* supplied, `parent_pherc.displayName` / `parent_cornice.displayName` is still populated as context, but `score` is `null`.
   - Data caveat: Casetta-style Cornici are stored as the abbreviation `"Cass.X"` (not `"Casetta X"`), so a literal `"Casetta"` query scores ~46 against `"Cass.7"` and returns nothing. The matcher is doing its job; the inputs just don't overlap. Tracked separately (synonym/alias handling vs. data re-load is undecided).

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
- `POST /search` - Complex search with multiple parameters (supports intersection of multiple criteria). The request body is the `SearchQuery` Pydantic model (all keys `snake_case`, all fields optional; unknown keys ignored), so the body schema is now introspectable in Swagger. The `display_name` filter is a strict regex (exact-name) match; to resolve a noisy displayName first, use `GET /resolve`. Note: keys were migrated from hyphenated to `snake_case` (e.g. `display-name` → `display_name`) and the `instituion` typo was fixed to `institution` — a breaking change to the request contract.
- `GET /resolve` - Fuzzy-resolve a noisy PHerc/Cornice/Pezzo displayName to ranked candidates. Query params: `name` (required), `label` (`PHerc` | `Cornice` | `Pezzo`, default `PHerc`), `parent_pherc`, `parent_cornice`, `threshold` (default 75), `limit` (default 10). Returns a JSON list with `displayName`, `name`, `score`, `nodeID` (Neo4j element ID), `parent_pherc`, `parent_cornice`. Empty result returns `200 []` (discovery endpoint, not "fetch this thing"); invalid `label` returns 400.
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
- Older `name` property is deprecated; `human_name` is no longer set by current loaders
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
- `scan_loader.py` normalizes the `complete` CSV column case-insensitively to `"True"` / `"False"` / `"unknown"`. With `--replace` (default) it wipes and reloads PGSRaw/SpectralRaw, MERGE-ing on the scan `uuid`, so all nodes carry the canonical `complete` and the 2026 integer count columns after a reload
- `metadata_loader.py` detects sentinel `Replacement UUID` values (anything that isn't a real UUID, e.g. `"discarded"` or `"."`) and flags the original EduceLabID as `retired = true` instead of creating a bogus successor node

### CSV Anomalies and Data Review
- `docs/data_review_notes.md` tracks CSV anomalies and modelling questions awaiting papyrologist confirmation (multi-row UUIDs, hard-coded loader edge cases, name-form inconsistencies). Add new entries there when you encounter data that the loaders pass through faithfully but that a domain expert should verify; update or remove entries once resolved.

## Claude Code Instructions

### Planning Mode
When in planning mode, write the proposed plan to an `.md` file under `./.claude/` (NOT just to `~/.claude`) for review before implementation. The `.claude/` directory is gitignored and used for Claude-generated plans and drafts.
