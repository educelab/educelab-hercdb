# Changelog

All notable changes to this project will be documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
