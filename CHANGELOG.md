# Changelog

All notable changes to this project will be documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.3] - 2026-08-27

### Added
- `GET /datasets/{proc_type}/unprocessed` and `GET /datasets/{proc_type}/ambiguous`, plus `HercClient.get_unprocessed_datasets(proc_type)` / `get_ambiguous_datasets(proc_type)` and `GraphDBConnection.find_unprocessed_datasets(proc_type)` / `find_ambiguous_datasets(proc_type)` — the 0.3.2 spectral work-list, parameterized by proc_type so PGS (and later REG/WEB) share one query family rather than gaining a hard-coded sibling apiece. `proc_type` is `SPEC` or `PGS`; the path segment is case-insensitive, and anything without a work-list returns 400.

### Changed
- Nothing in the returned rows. The work-list row is byte-identical to 0.3.2's, so nothing to migrate.
- Internally, `_spectral_candidate_rows` → `_raw_candidate_rows(proc_type)`, `_spectral_rows_by_scan` → `_candidate_rows_by_scan`, `_public_spectral_row` → `_public_candidate_row`. Neo4j cannot parameterize a node label, so the query interpolates one looked up from `_CANDIDATE_LABELS` rather than taken from the caller — injection is structurally impossible, not merely unlikely.

### Backward compatibility
- `GET /datasets/spectral/unprocessed` and `/datasets/spectral/ambiguous` are unchanged and still declared *before* the parameterized routes, so FastAPI keeps matching them first and 0.3.2 clients are unaffected.
- `find_unprocessed_spectral_datasets()` / `find_ambiguous_spectral_datasets()` and the two matching `HercClient` methods remain. The client aliases deliberately still call the *literal* spectral routes, so a 0.3.3 client also works against a server that has not been upgraded yet.

---

## [0.3.2] - 2026-08-12

### Added
- `GET /datasets/spectral/unprocessed` + `HercClient.get_unprocessed_spectral_datasets()` — the work-list for the unattended spectral dispatcher: one row per artifact, its newest complete scan, carrying the dataset path plus the `pherc`/`cornice`/`pezzo` fields an output directory is named from, and `attempts`/`last_status`/`last_notes` for a retry cap. Three selection rules whose **order matters**: skip multi-object trays, take newest-per-artifact, *then* drop anything already carrying a `completed` SPEC Process. Dropping processed scans first would make the next-newest become "newest of the unprocessed", and the list would never empty.
- `GET /datasets/spectral/ambiguous` + `HercClient.get_ambiguous_spectral_datasets()` — complete scans the dispatcher skips, and why. Currently scans whose EduceLabID is assigned to more than one P.Herc.: their output has no single object directory to belong to, so a human decides where it lands. Reporting them is what stops them being silently dropped from a campaign.
- `notes` on the process-status update (`PUT /pipelines/{id}/processes/{proc_type}/status`, `update_process_status()`, `HercClient.update_process_status()`) — free text recording *where* a stage failed, for a stage split across several jobs where only the job that died knows which one it was. Optional throughout, and written only when given, so a later update without notes cannot blank a note another job just wrote.
- `GET /pipelines/{id}/stages` now returns `notes` on each stage.

### Changed
- Raw dataset paths are normalized to data-root-relative at ingest (`Dailies/` for PGS, `Dailies/Spectral/` for spectral) in `graph_loader`, rather than stored as the scan CSVs happen to record them. Idempotent, so re-running a load or loading a corrected CSV cannot double the prefix. Without this, `scan_loader --replace` (the default) would revert already-normalized paths on the next load.

---

## [0.3.0] - 2026-07-17

### Added
- `HercClient` automatically retries transient failures (connection errors, read timeouts, and `502`/`503`/`504`) with exponential backoff, and applies a per-request timeout. New constructor params `timeout`, `retries`, `backoff_factor`, `backoff_max` (defaults span ~108s, riding over the nightly Neo4j backup window). Retries cover all HTTP verbs because hercdb writes are idempotent (`MERGE`); `404`/`422` are never retried. Implemented with a single `requests.Session` + `HTTPAdapter(urllib3.Retry)` — no new dependency.
- Nightly Neo4j offline-backup tooling: `scripts/neo4j_backup.sh` (dumps both the `neo4j` and `system` databases while stopped, ships timestamped dumps to a cold-spare VM over SSH, prunes by retention, always restarts Neo4j via an EXIT trap, optional heartbeat) and the `docs/BACKUP.md` runbook (setup, cron schedule, monitoring, restore/DR, testing).
- `GET /pipelines/{id}/stages` now returns `input_dataset_paths` (list[str]) and `output_dataset_path` (str | None) on each stage. `get_pipeline_status()` traverses the existing `(input)-[:INPUT]->(proc)-[:OUTPUT]->(output)` relationships; a REG stage carries both its PGS and SPEC inputs. The stages endpoint and client are passthroughs, so no server/client change was needed.

### Changed
- REST API now returns **HTTP 503** with a `Retry-After: 60` header (instead of a misleading `404`) when Neo4j is unreachable — e.g. during the nightly offline backup or a restart. `GraphDBConnection._run_query` re-raises `ServiceUnavailable`/`SessionExpired` as the new `DatabaseUnavailableError` (exported from `educelab.hercdb.db`); an app-wide handler maps it to 503. The `None`→`404` path is preserved for genuinely empty query results.

### Infrastructure
- Migrated CI from GitLab to GitHub Actions: a build/import smoke test across Python 3.10–3.12 (`uv`) plus sdist/wheel build and `twine check`, and a PyPI publish workflow (trusted publishing via OIDC) triggered on `v*` tags and manual dispatch. Declared `pydantic` explicitly in the server extra (previously only transitive via FastAPI); pointed the Repository URL at GitHub.

---

## [0.2.2] - 2026-06-29

### Added
- `el-hercdb-pipeline-cleanup` CLI (`cli/cleanup_pipelines.py`): DB-admin tool to delete pipeline records by id (talks straight to Neo4j, no REST server). `--list` shows every pipeline + its artifact; passing one or more pipeline ids deletes each (Pipeline + Process + output dataset nodes; raw/input datasets untouched). Companion to the acquisition-workflow pipeline-recording write path.

### Fixed
- `initialize_process()` PGS/SPEC stages now match the raw input dataset across the pipeline EduceLabID's `[:REPLACES*0..]` chain, mirroring `find_datasets_for_educelabid_with_predecessors()`. A pre-replacement scan that still `BELONGS_TO` a predecessor UUID is now recorded correctly instead of being skipped. REG/WEB match this pipeline's own output nodes and were unaffected.

---

## [0.2.1] - 2026-06-22

### Added
- `parent` field on each Cornice/Pezzo in `GET /subdivisions` response (`{type, displayName}`, or `null` for the PHerc itself), so a nested Pezzo can be rendered under its Cornice without a second lookup.

---

## [0.2.0] - 2026-06-22

### Added
- `displayName` + `aliases` name model on PHerc/Cornice/Pezzo: one canonical display name, plus a deduplicated `aliases` array covering all known forms (legacy `name`, Casetta synonyms, spelling variants). Full-text index `artifact_names` covers both fields.
- Casetta synonyms auto-generated in `aliases` (`Cass.N`, `Casetta N`, `Casetto N`) so all spelling variants resolve to the canonical node at score 100.
- `:Casetta` label applied to PHerc nodes that are organised as cassette.
- Disegni (historical drawings) support in the graph loader.
- `fuzzy_find_node()` — standalone ranked-candidate primitive scoring against `displayName` + all `aliases`; exact match short-circuits to score 100.
- `GET /resolve` endpoint: fuzzy-resolves a noisy name to ranked candidates (the only fuzzy entry point in the REST API).
- `GET /artifacts?pherc=&cornice=&pezzo=` — full artifact detail by exact name (own props, metadata, assigned `educelabids`, child counts). Replaces the removed per-node endpoints.
- `GET /artifacts/{uuid}` — lightweight UUID → artifact bridge (`{type, displayName, pherc, cornice, pezzo, parent, location}`).
- `el-hercdb-scan-report` CLI (`scan_completeness.py`): generates `scan_completeness_full.csv` and `scan_completeness_issues.csv`; `--scans-from-csv` mode reads coverage directly from scan CSVs without loading them into the DB.
- 2026 scan CSV columns parsed onto PGSRaw/SpectralRaw nodes: `file_count`, `missing_files`, `zero_byte_files`, `short_files`, `bad_format_files`.
- `normalize_complete()` in `scan_loader.py` collapses `complete` CSV variants to canonical `"True"` / `"False"` / `"unknown"`.
- `--replace` / `--no-replace` flag in scan loader; default wipes and reloads PGSRaw/SpectralRaw before each run (FlatbedScanDataset untouched). MERGE on scan `uuid` makes reloads idempotent.
- `mark_educelabid_retired()` in `metadata_loader.py`: sentinel `Replacement UUID` values (e.g. `"discarded"`, `"."`) set `retired = true` on the original EduceLabID instead of creating a bogus successor node.
- `GET /subdivisions` now returns `aliases` and `educelabids` per node.

### Changed
- Package restructured into `db/`, `rest/`, `client/`, `loader/`, `cli/` submodules; old flat import paths kept as backward-compatible aliases.
- `find_datasets_for_educelabid_with_predecessors()` and `find_all_datasets_for_pherc()` pool datasets across the full `[:REPLACES*0..]` chain; each dataset carries `belongs_to_uuid`.

### Removed
- `POST /search` endpoint and associated `find_pherc_by_*` query methods (superseded by `GET /resolve`).
- Per-node REST endpoints: `GET /pherc/{id}`, `.../cornice/{id}`, `.../pezzo/{id}`, `.../datasets/{type}`, `.../educelabids` (superseded by `/artifacts`, `/all-datasets`, `/subdivisions`).
- `get_directly_attached_nodes()` / `records_to_label_json()` / `find_datasets()` / `find_educelabids_for_pherc()` from `GraphDBConnection`.

---

## [0.1.1] - 2025-02-24

### Fixed
- Submodule dependencies not included in package distribution.
- Record type key retrieval bug in query results.
- Driver initialisation check to prevent use before connection is established.

---

## [0.1.0] - 2024-07-23

### Added
- Initial pip-installable release of `educelab-hercdb`.
- `GraphDBConnection` class with Neo4j query methods for PHerc, Cornice, Pezzo, EduceLabID, and Dataset nodes.
- FastAPI REST API with token-based authentication (`~/.tokens`).
- Data loading utilities: `graph_loader.py` (PHerc hierarchy), `metadata_loader.py` (author, language, custodial institution, UUID assignment), `scan_loader.py` (flatbed, PGS, spectral datasets).
- Pipeline CRUD: create, update, delete pipelines and process stages; query status and summaries.
- `HercClient` Python client wrapping all REST endpoints.
- Configuration via environment variables (`EDUCEDB_URI` / `EDUCEDB_USER` / `EDUCEDB_PASSWORD`), `~/.educedb` TOML file, or interactive prompt.
