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
uv run python -m unittest tests.integration.test_db_queries.TestPhercDbQueries.test_find_artifact_name_by_uuid

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
- `el-hercdb-scan-report` — scan-completeness CSV report (`cli/scan_completeness.py`); writes a full report and an issues-only report, walking the PHerc hierarchy plus any `REPLACES` chains. Run via `uv run el-hercdb-scan-report --out-dir ./tmp`. By default coverage comes from loaded PGSRaw/SpectralRaw **nodes**. With `--scans-from-csv` (plus `--pgs-csv`/`--spectral-csv`, ground-truth defaults) coverage is read **directly from the scan CSVs** — **read-only on the DB, no scan-load required** — and a third `scan_completeness_review.csv` of wrong/missing/inconsistent entries is written (suppress with `--no-review`). Each row carries the **museum** (`Institution`) column.
- `el-hercdb-sample-uuid-check` — cross-checks each scan's `sample uuid` against the artifact named in its `path` (`cli/sample_uuid_check.py`); read-only, writes a categorized text report. The same module exposes `load_scan_rows`/`cross_check`, reused by the `--scans-from-csv` report.
- `el-hercdb-pipeline-cleanup` — DB-admin tool to delete pipeline records by id (`cli/cleanup_pipelines.py`); talks straight to Neo4j (no REST server). `--list` shows every pipeline + its artifact; passing one or more `uber_job_id`s deletes each via `db.delete_pipeline` (Pipeline + Process + output dataset nodes; raw/input datasets untouched). Companion to the acquisition-workflow `submit_uber_pipeline.py` pipeline-recording write path, which records every (dry-run or real) submission keyed by `uber_job_id`.

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
- `get_artifact_info(pherc, cornice, pezzo)`: full artifact detail by exact name (own props + metadata + assigned `educelabids` + child counts), backs `GET /artifacts?...`. `find_artifact_location_by_uuid(uuid)`: the UUID → artifact bridge, backs `GET /artifacts/{uuid}`. Both added in the API consolidation that removed `get_directly_attached_nodes`/`records_to_label_json`/`find_datasets`/`find_educelabids_for_pherc`.
- Key enums: `DatasetType` (FlatbedScan, PGSRaw, SpectralRaw)

**src/educelab/hercdb/config.py**: Configuration management
- Loads settings from environment variables, `~/.educedb` file, or prompts
- Uses `tomllib` (Python 3.11+) or `configparser` (Python 3.10)

**src/educelab/hercdb/rest/server.py**: FastAPI REST API
- Token-based authentication using `~/.tokens` file
- One `/artifacts` resource for PHerc/Cornice/Pezzo artifacts — by name (`?pherc=&cornice=&pezzo=`, full detail) or by UUID (`/{uuid}`, location bridge); plus `/subdivisions`, `/all-datasets`, `/educelabid/{uuid}/datasets`, `/resolve`
- `/resolve` endpoint fuzzy-resolves a noisy displayName to ranked candidates (the only fuzzy entry point; fetch endpoints match `displayName` exactly)

**src/educelab/hercdb/loader/graph_loader.py**: Database loading utilities
- `PhercGraphDatabaseLoader`: Class for bulk data loading operations
- `mark_educelabid_retired(uuid, reason)` sets `retired = true` and stores a reason string on an EduceLabID; called by `metadata_loader.py` when a Replacement UUID is a sentinel like `"discarded"` or `"."` rather than a real UUID

**src/educelab/hercdb/loader/scan_loader.py**: Scan-data loader
- Loads the 2026 scan schema: PGS and Spectral CSVs both carry `file count, missing files, zero-byte files, short files, bad format files` (parsed as ints onto the nodes as `file_count, missing_files, zero_byte_files, short_files, bad_format_files`). The Spectral `sample uuid 2` column was dropped in 2026; the loader no longer reads it.
- `normalize_complete(raw)` collapses CSV `complete` variants (`"TRUE"` / `"True"` / `"true"` / etc.) to the canonical strings `"True"`, `"False"`, or `"unknown"` so PGS and Spectral nodes share the same `complete` semantics. The canonical strings always satisfy the loader's `if complete:` guard, so re-runs overwrite stale values in either direction.
- `--replace` (default on; `--no-replace` to disable) calls `loader.delete_all_scan_nodes()` to DETACH DELETE all PGSRaw/SpectralRaw nodes before reloading (FlatbedScanDataset untouched). `add_pgs_raw_node` / `add_spectral_raw_node` MERGE on the scan `uuid` alone (a unique key) and SET `path`/`date_start`/counts, so a changed path updates the node in place rather than duplicating it — the load is idempotent.
- The 2023 → 2026 reconciliation that produced the spectral ground-truth file (`input_data/spectral_datasets_20260601_reconciled.csv`) is recorded in `docs/data_review_notes.md` §5 (78 backfilled sample uuids, 147 unlinked calibration/test scans, 1 dropped `sample uuid 2`).

**src/educelab/hercdb/cli/scan_completeness.py**: Scan-completeness report CLI
- Generates `scan_completeness_full.csv` and `scan_completeness_issues.csv` (and, in `--scans-from-csv` mode, `scan_completeness_review.csv`)
- Wired up as the `el-hercdb-scan-report` shell command via `[project.scripts]`
- Walks `REPLACES` so pre-replacement scans on retired predecessor UUIDs still count toward an artifact's coverage
- A dataset counts as **complete** only when `complete == "True"` AND `missing_files == 0 AND zero_byte_files == 0 AND short_files == 0 AND bad_format_files == 0` (see `_is_fully_complete`). This is stricter than the raw `complete` flag and is local to this report — `find_datasets_for_educelabid` / `find_datasets_for_educelabid_with_predecessors` / `find_all_datasets_for_pherc` still filter on the raw flag Cypher-side and need reconciling (tracked in memory).
- **Two coverage sources.** Default: loaded PGSRaw/SpectralRaw nodes via `classify()`. `--scans-from-csv`: coverage read directly from the scan CSVs (`load_scan_rows` + `build_coverage` + `classify_from_csv`), pooling scans across each UUID's `REPLACES` chain via `db.find_predecessor_uuid_map()`. The CSV path is **read-only on the DB and needs no scan-load** — used to answer "what still needs scanning + which museum" before the new scans are loaded. Both apply the same strict `_is_fully_complete` / `sample_uuid_check.is_row_complete` rule. **Artifact attribution is always by `sample uuid` → exact Neo4j node**, so `118a`/`118b` (distinct PHerc nodes, distinct UUIDs) are never conflated; the path is used only for the cross-check.
- **Review report** (`--scans-from-csv` only): flags **sample-uuid data errors only** — `WRONG_SAMPLE_UUID` and `ORPHAN_SAMPLE_UUID` (both high, scan-side from `sample_uuid_check.cross_check`). Deliberately **excluded**: `INCOMPLETE_FILES` (scanned-but-not-good artifacts — they already appear in the issues CSV with an `incomplete` status, so not duplicated here) and `UNLINKED_UUID` (minted UUIDs with no artifact — out of scope for "what needs scanning"; `db.find_unassigned_educelabids()` still exists for that lookup but is no longer called). Note: the cross-check compares PHerc number **sets**, so it cannot detect an `118a`↔`118b` swap (paths omit the alpha suffix); documented in `cli/sample_uuid_check.py`.

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
- **Name model (PHerc/Cornice/Pezzo)**: each carries a single canonical `displayName` (always populated, the only name shown to users) plus an `aliases` string-array — the de-duplicated set of every known form (displayName + uuid-sheet `name` + Casetta synonyms + spelling variants). `aliases` is the match surface; resolution goes through `fuzzy_find_node` (which scores against displayName + aliases) and a full-text index `artifact_names` on `[displayName, aliases]`. See "Display Names vs Internal Names" and the name-model plan in `.claude/plans/name_displayname_alias_model.md`.
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

1. **Name resolution** (resolve a noisy/approximate displayName to nodes):
   - `fuzzy_find_node(name, label, parent_pherc, parent_cornice, threshold, limit)` — ranked candidates against displayName + aliases (see "Fuzzy name lookup" below). The old per-property `find_pherc_by_*` lookups (display_name, author, language, property_value, numeric_property, unrolled_year, etc.) were removed along with the `POST /search` endpoint.

2. **Dataset queries** (both REST dataset endpoints pool the `[:REPLACES*0..]` chain and tag each dataset with `belongs_to_uuid`):
   - `find_datasets_for_educelabid_with_predecessors(uuid, ds_type=None, newest_completed=False)` - datasets for a UUID, pooled across its REPLACES chain; each dataset carries `belongs_to_uuid` (the EduceLabID it actually belongs to). Backs `GET /educelabid/{uuid}/datasets` **and** the scan-completeness report.
   - `find_datasets_for_educelabid(uuid, ds_type=None, newest_completed=False)` - single-UUID view (no chain pooling). Retained as a primitive; not wired to a REST endpoint.
   - `find_all_datasets_for_pherc(pherc_display_name, ds_type=None, newest_completed=False)` - all datasets grouped by the active/assigned EduceLabID, chain-pooled, each dataset carrying `belongs_to_uuid`.
   - `find_all_artifacts_and_educelabids_for_pherc(pherc_display_name)` - one record per (artifact, UUID) pair, plus a sentinel record for any artifact with no UUID. Suppresses the PHerc-itself row when the PHerc has Cornici/Pezzi children but no direct UUID. Used by the scan-completeness report.
   - (Removed: `find_datasets` and `find_educelabids_for_pherc` — along with the `/datasets/{type}` and `/educelabids` endpoints they backed.)

3. **Artifact detail & traversal**:
   - `get_artifact_info(pherc, cornice=None, pezzo=None)` - full detail for one artifact by exact displayName: own props, attached metadata grouped by label, assigned `educelabids`, and child counts (`cornici_count`/`pezzi_count`). No datasets. Backs `GET /artifacts?pherc=...`. Returns `None` if not found.
   - `list_cornici_and_pezzi_for_pherc(pherc_display_name)` - full hierarchy of Cornici and Pezzi; returns `{pherc, cornici, pezzi}` where each node is `{displayName, aliases, educelabids, parent}`. `parent` is `{type, displayName}` — a nested Pezzo's parent Cornice, or the PHerc for a directly-attached node (and `None` for the PHerc itself) — so consumers can render a Pezzo under its Cornice. Backs `GET /subdivisions`. Returns `None` if the PHerc doesn't exist.
   - (Removed: `get_directly_attached_nodes` / `records_to_label_json`, which backed the old per-node endpoints. The deprecated `list_cornici_pezzi` is still present pending search-CLI cleanup.)

4. **UUID lookups**:
   - `find_artifact_name_by_uuid(uuid)` - returns dict with `pherc`, `cornice`, `pezzo` display names for a UUID (used internally by pipeline summaries).
   - `find_artifact_location_by_uuid(uuid)` - the UUID → artifact bridge: `{type, displayName, pherc, cornice, pezzo, parent}`. Backs `GET /artifacts/{uuid}` (the handler adds `uuid` + a composed `location`).

5. **Pipeline queries**:
   - `find_pipelines()` - returns list of all pipelines with their `pipeline_id` and `artifact_uuid`
   - `get_pipeline_status(pipeline_id)` - returns list of process stages with `start_time`, `end_time`, `stage`, `status`, `slurm_id`, plus `input_dataset_paths` (list[str], gathered from `-[:INPUT]->` dataset nodes — REG carries both its PGS + SPEC inputs) and `output_dataset_path` (str | None, from the single `-[:OUTPUT]->` node)
   - `get_all_pipeline_summaries()` - returns all pipelines with aggregated status info

6. **Pipeline CRUD**:
   - `initialize_pipeline(pipeline_id, artifact_uuid, datetime)` - create a Pipeline node linked to an EduceLabID
   - `initialize_process(pipeline_id, proc_type, input_dataset_paths, output_dataset_path, slurm_id, start_datetime)` - create a Process node (PGS, SPEC, REG, WEB) with input/output dataset links
   - `update_process_status(pipeline_id, stage, status, end_datetime)` - update process status to completed or failed
   - `delete_pipeline(pipeline_id)` - delete a Pipeline, all its Process nodes, and output dataset nodes (leaves input datasets untouched)
   - `get_pipeline_confirmation(pipeline_id)` - full pipeline summary with all stages

7. **Fuzzy name lookup** (`src/educelab/hercdb/db/connection.py`):
   - `fuzzy_find_node(name, label="PHerc", parent_pherc=None, parent_cornice=None, threshold=75, limit=10)` — standalone reusable primitive that returns ranked candidates: `[{"node", "displayName", "score", "parent_pherc", "parent_cornice"}, ...]` ordered by score desc. Use this when callers have a noisy name (typos, extra spaces, alternate spellings) and need to identify the right PHerc/Cornice/Pezzo before reaching for UUIDs/EduceLabIDs and the other `find_*` methods. **Do not** add per-endpoint fuzzy variants — compose with this method.
   - Implementation notes: normalizes by stripping **all** whitespace + lowercasing both query and candidate before scoring; scores against the **max** over a node's displayName + every `aliases` member (so any alternate form matches); exact match after normalization short-circuits to score 100 (all candidates sharing the normalized form are returned). Uses `rapidfuzz.fuzz.ratio` (not `WRatio`) — `ratio` penalizes length mismatch, which works correctly for the mostly-short identifier-style displayNames in this dataset; `WRatio`'s partial-ratio component over-scored short substrings of the query. Among equal-score candidates, substring matches (query appears verbatim in any form) sort before non-substring matches — e.g. "118a"/"1180" rank above "1168" for query "118", and "Cass."/"Cassetta" rank above unrelated names for query "cass". Alphanumeric suffix names like "118a" still require `limit ≥ 13` to appear when there are many numeric substring matches ("1118", "1180"–"1189") sorting before them alphabetically.
   - Parent semantics: for `Cornice`/`Pezzo`, the resolver recursively fuzzy-resolves any supplied parent name and scopes the child candidate fetch to those parents. Parent scores are reported separately on each result (not fused with the child score). When a parent name was *not* supplied, `parent_pherc.displayName` / `parent_cornice.displayName` is still populated as context, but `score` is `null`.
   - Casetta resolution (resolved): the loader now stores Casetta synonyms in `aliases` — for any numbered casetta it generates `Cass.N`, `Casetta N`, **and** `Casetto N` (the loader recognizes all of `Cass.`/`Casetta`/`Casetto`/`Cassetta`/`Cassetto` followed by a number; the bare word "Cassetto" with no number is left alone). So `"Casetta 20"`, `"Casetto 20"`, and `"Cass.20"` all resolve to the `Cass. 20` node at score 100, and a double-s `"Cassetto 20"` query still matches via fuzzy (~95). Synonym generation lives in `PhercGraphDatabaseLoader._casetta_synonyms` / `_expand_aliases`; the one-time migration that backfilled existing data is `preprocessing/migrate_name_aliases.py`.

### REST API Endpoints

Protected by Bearer token authentication (tokens in `~/.tokens`):

A **PHerc / Cornice / Pezzo is an "artifact"**, addressed on one `/artifacts` resource two ways: **by name** (query params, full detail) or **by UUID** (path, lightweight location bridge). The two personas the API bridges via UUID: papyrologists arrive by name, computer scientists by UUID. By-name fetch endpoints match `displayName` **exactly** — resolve noisy input with `/resolve` first (fuzzy matching lives only there).

- `GET /check-token` - Verify token validity
- `GET /artifacts?pherc=&cornice=&pezzo=` - Full detail for one artifact by exact name (own props, metadata, assigned `educelabids`, child counts; no datasets). `pherc` required; missing → 422, not found → 404. Backed by `get_artifact_info`.
- `GET /artifacts/{uuid}` - Resolve a UUID to its artifact: `{uuid, type, displayName, pherc, cornice, pezzo, parent, location}`. Backed by `find_artifact_location_by_uuid`.
- `GET /pherc/{pherc_id}/subdivisions` - List all Cornici and Pezzi (full hierarchy); each node is `{displayName, aliases, educelabids, parent}` (`parent` = `{type, displayName}`, or `None` for the PHerc — a nested Pezzo carries its parent Cornice).
- `GET /pherc/{pherc_id}/all-datasets` - All datasets grouped by active/assigned EduceLabID, pooled across REPLACES chains; each dataset carries `belongs_to_uuid`. Optional `dataset_type` / `newest_completed`.
- `GET /educelabid/{uuid}/datasets` - Datasets for a UUID, pooled across its REPLACES chain; each carries `belongs_to_uuid`. Optional `dataset_type` / `newest_completed`.
- `GET /resolve` - Fuzzy-resolve a noisy PHerc/Cornice/Pezzo displayName to ranked candidates. Query params: `name` (required), `label` (`PHerc` | `Cornice` | `Pezzo`, default `PHerc`), `parent_pherc`, `parent_cornice`, `threshold` (default 75), `limit` (default 10). Returns a JSON list with `displayName`, `name`, `score`, `nodeID` (Neo4j element ID), `parent_pherc`, `parent_cornice`. Empty result returns `200 []` (discovery endpoint, not "fetch this thing"); invalid `label` returns 400.
- (Removed in the API consolidation: `GET /pherc/{pherc_id}`, `.../cornice/{cornice_id}`, `.../pezzo/{pezzo_id}`, `.../cornice/{cornice_id}/pezzo/{pezzo_id}`, `.../datasets/{dataset_type}`, `.../educelabids` — superseded by `/artifacts`, `/all-datasets`, and the enriched `/subdivisions`.)
- `GET /pipelines` - Get all pipelines with status summaries
- `GET /pipelines/{pipeline_id}/stages` - Get all process stages for a pipeline; each stage carries `input_dataset_paths` (list) and `output_dataset_path` (scalar, or null) alongside `proc_type`/`status`/`slurm_id`/`start_time`/`end_time`
- `POST /pipelines` - Create a new pipeline linked to an EduceLabID
- `POST /pipelines/{pipeline_id}/processes` - Create a new process (stage) within a pipeline
- `PUT /pipelines/{pipeline_id}/processes/{proc_type}/status` - Update process status
- `DELETE /pipelines/{pipeline_id}` - Delete a pipeline and all its processes and output datasets
- `GET /pipelines/{pipeline_id}/confirmation` - Get full pipeline summary with all stages

**Note:** The REST API renames the `stage` field to `proc_type` in pipeline stage responses to avoid ambiguity with pipeline stage ordering.

## Important Notes

### Display Names vs Internal Names
- **`displayName`** is the single canonical, user-facing name on every PHerc/Cornice/Pezzo (e.g. "421", "118a", "Cass. 20") and is **always populated**. It is the only name to display.
- **`aliases`** (string array) is the match surface: the de-duplicated set of all known forms (displayName + the legacy uuid-sheet `name` + Casetta synonyms + spelling variants). Never display from `aliases`; use it only to *resolve* a possibly-noisy input to a node. Loaders append to `aliases` (they don't overwrite); `fuzzy_find_node` scores against it (matching displayName **or** any alias, with exact matches short-circuiting to score 100); a full-text index `artifact_names` covers `[displayName, aliases]`.
- Older `name` property is deprecated (kept as one of the alias sources during transition); `human_name` is no longer set by current loaders.
- Methods marked "Soon to be deprecated" should be avoided in new code.
- The canonical-displayName + aliases model, the one-time migration (`preprocessing/migrate_name_aliases.py`), and the duplicate-node merge are described in `.claude/plans/name_displayname_alias_model.md`.

### Naming Inconsistency: `stage` (Neo4j) vs `proc_type` (Python/REST)
- The Python API and REST layer use `proc_type` as the parameter/field name for process types (PGS, SPEC, REG, WEB).
- However, the Neo4j `Process` nodes still store this value under the property name `stage` in Cypher queries (e.g., `{stage: "PGS"}`).
- This mismatch should be reviewed and potentially reconciled in a future update.

### Query Methods
- Most find methods perform case-insensitive partial matching using Cypher regex: `(?i).*{value}.*`
- Results are typically ordered by `ph.displayName`

### Python Version Support
- Minimum: Python 3.10
- Config loading differs between 3.10 (configparser) and 3.11+ (tomllib)

### Data Loading
- `educelab.hercdb.loader` module contains utilities for bulk operations
- `preprocessing/` has Jupyter notebooks for data preparation from Google Sheets
- `scan_loader.py` normalizes the `complete` CSV column case-insensitively to `"True"` / `"False"` / `"unknown"`. With `--replace` (default) it wipes and reloads PGSRaw/SpectralRaw, MERGE-ing on the scan `uuid`, so all nodes carry the canonical `complete` and the 2026 integer count columns after a reload
- `metadata_loader.py` detects sentinel `Replacement UUID` values (anything that isn't a real UUID, e.g. `"discarded"` or `"."`) and flags the original EduceLabID as `retired = true` instead of creating a bogus successor node

### CSV Anomalies and Data Review
- `docs/data_review_notes.md` tracks CSV anomalies and modelling questions awaiting papyrologist confirmation (multi-row UUIDs, hard-coded loader edge cases, name-form inconsistencies). Add new entries there when you encounter data that the loaders pass through faithfully but that a domain expert should verify; update or remove entries once resolved.

## Claude Code Instructions

### Planning Mode
When in planning mode, write the proposed plan to an `.md` file under `./.claude/` (NOT just to `~/.claude`) for review before implementation. The `.claude/` directory is gitignored and used for Claude-generated plans and drafts.
