# Changelog

All notable changes to this project will be documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.5] - 2026-09-14

### Fixed
- `initialize_process` records REG and WEB stages whose inputs were produced by a **different** pipeline. Both branches previously required the input to already hang off a Process in the *same* pipeline (`MATCH (ppline)<-[:STAGE_OF]-(:Process)--(pg_proc:PGSProcessed {path: ...})`). A registration- or webify-only submission mints a fresh `uber_job_id` whose only stage is REG (or WEB), while its `PGSProcessed`/`SpectralProcessed`/`Registered` inputs came from an earlier pipeline — so the MATCH found nothing, `initialize_process` returned `None`, and the caller was left with a Pipeline node holding zero Processes. The jobs ran fine; hercdb simply never learned what they were.
- Inputs are now matched by `path` alone, which is the key those nodes are MERGEd on and their unique address everywhere else. This is the same shape as the 0.2.2 change that made PGS/SPEC match their raw scan across the EduceLabID's `REPLACES` chain: the input's identity does not depend on which pipeline is consuming it. The input `MATCH` is still required, so a genuinely missing input continues to return `None` rather than recording a Process with nothing feeding it. (0.2.2 recorded that REG/WEB "match this pipeline's own output nodes and were unaffected" — that held only because no registration-only submission had been made yet.)

### Changed
- The REST app's advertised `version` is read from installed package metadata (`educelab.hercdb.__version__`) instead of a hand-copied literal. It had been pinned at `"0.3.2"` since 0.3.2 — the bump was missed on both 0.3.3 and 0.3.4, so `/docs` and `/openapi.json` had been misreporting the server version for two releases. `__version__` is now exported from the package, so clients can read it too; it falls back to `"0.0.0+unknown"` when running from a source tree with no install.

### Fixed (tests)
- `test_find_datasets_for_educelabid` asserted the returned `type` was one of the three raw labels. 0.3.4 made processed outputs surface through that query, so a real `SpectralProcessed` in the database tripped an assertion that had simply not been updated. It now accepts the full `DatasetType` range.


### Backward compatibility
- No schema, API surface or result shape changes. A REG/WEB submission whose inputs *were* produced by the same pipeline — the only case that worked before — still records exactly the same nodes and relationships.
- Downstream effect worth knowing: acquisition-workflow's headless path compares recorded stages against submitted ones, so every unattended registration batch previously exited `EXIT_PARTIAL` (1), telling the caller to reconcile a batch that had actually queued cleanly. Those batches now tally correctly.

---

## [0.3.4] - 2026-09-14

### Added
- `DatasetType.PGSProcessed`, `DatasetType.SpectralProcessed`, `DatasetType.Registered` and `DatasetType.WebProcessed` — every pipeline output label — accepted everywhere a `dataset_type` filter is (the `/pherc/{id}/all-datasets` and `/educelabid/{uuid}/datasets` query param, `HercClient.get_all_datasets_for_pherc` / `get_datasets_for_educelabid`, and the three `GraphDBConnection.find_*datasets*` methods). The node labels already existed — `initialize_process` has always written them — but nothing could read them back out.
- Processed datasets now appear in the dataset results by default, alongside raw scans. Each carries `pipeline_id` and `status` from the Process that produced it, a `date_end` taken from that Process's `end_time`, and a `complete` flag — the same `"True"`/`"False"` string `normalize_complete` writes on raw scans, derived from whether the Process finished. Downstream consumers (acquisition-workflow's `common.dataset_status`) gate every dataset on `complete`; without it processed rows read as incomplete and vanish from pickers silently.
- Raw scans keep their own `complete` straight from the CSV. It is **not** backfilled from the stricter flag-plus-file-counts predicate, which would change raw semantics.

### Changed
- The three dataset queries now union two traversals instead of one. A raw scan hangs off an EduceLabID directly (`BELONGS_TO`); a processed dataset does not — it is a Process output, reached via `EduceLabID <-[:FOR]- Pipeline <-[:STAGE_OF]- Process -[:OUTPUT]-> d`. `_dataset_sources_cypher(anchor)` emits both branches with one projection (`d`, `date_end`, `is_complete`, `pipeline_id`, `proc_status`), so the filtering and grouping downstream are unchanged.
- **Requires Neo4j 5.23 or newer** (production runs 5.26.30). `_dataset_sources_cypher` uses the scoped `CALL (anchor) { ... }` variable-scope clause; the older importing-`WITH` spelling still parses but logs a deprecation notification on every dataset query.
- `newest_completed` means "the Process finished" for a processed dataset — it has no `complete` flag or file counts of its own. For raw scans the rule is untouched (`_FULLY_COMPLETE_PREDICATE`, still the twin of `scan_completeness._is_fully_complete`).

### Fixed
- `_serialize_dataset` identifies a processed row by its **label** (`ds_type in _PROCESSED_DATASET_LABELS`) rather than by the presence of a Process property. Gating on `pipeline_id` (or `proc_status`) keys off a field that merely happens to be populated — `initialize_pipeline` MERGEs on `pipeline_id`, so it is always set today, but a row without one would silently lose its status, timing and completeness, and a processed dataset with no `complete` disappears downstream. The label *is* the branch: the two halves of `_dataset_sources_cypher` are partitioned by label.
- The newest-per-type grouping in `find_all_datasets_for_pherc` compares `(ds.get('date_end') or '')`. A processed row can carry an explicit `date_end` of `None` (an unfinished Process), which raw rows never produced; `None > str` raises rather than sorting.

### Backward compatibility
- Raw-scan results are unchanged in shape and content. Callers that pass an explicit raw `dataset_type` (the scan-completeness report does, for both modalities) see nothing new.
- Callers that pass **no** `dataset_type` and assume every row is a raw scan will now also see processed rows; filter on `type` or pass `dataset_type` explicitly.
- `Registered` and `WebProcessed` are exposed but match nothing in the current database: a survey of 161 pipelines (all 41 non-completed plus 120 sampled completed) found every pipeline carries exactly one stage, only ever `PGS` or `SPEC`. They are wired for when REG/WEB stages start running.

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
