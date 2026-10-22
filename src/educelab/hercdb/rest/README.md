# REST API

FastAPI-based REST API for querying the Herculaneum Papyrus Scroll Database.

## Running the Server

### Development

```shell
uv run uvicorn educelab.hercdb.rest.server:app --reload
```

The `--reload` flag watches for source file changes and automatically restarts the server. Only use this during development.

Interactive docs are available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Production

For full server setup (credentials, tokens, systemd), see [docs/SERVER_SETUP.md](../../../../docs/SERVER_SETUP.md).

## Authentication

All endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

Tokens are loaded from `~/.tokens`. Each line has the format `username = token`.

## Error Responses

Status codes used across all endpoints:

| Code | Meaning |
|------|---------|
| `200` / `201` | Success (`201` on resource creation) |
| `400` | Bad request (e.g. invalid `label` or `proc_type`) |
| `401` | Missing or invalid Bearer token |
| `404` | The requested resource does not exist (artifact/UUID/pipeline not found) |
| `422` | Missing/invalid query params or request body (e.g. `pherc` omitted) |
| `503` | **Neo4j is unreachable** — a transient infrastructure failure |

### 503 Service Unavailable

Returned when the server cannot reach Neo4j — for example during the brief nightly
offline backup, or a DB restart. It is deliberately **distinct from `404`**: a `404`
means "this thing doesn't exist," while `503` means "the database is temporarily down,
try again."

The response carries a `Retry-After: 60` header:

```json
{ "detail": "Database temporarily unavailable; please retry." }
```

Clients should **retry on `503`** (and other `5xx`) but **not** on `404`/`422`. All
write endpoints are idempotent (`MERGE`-based), so a retried create/update will not
duplicate data. The bundled `HercClient` does this automatically (retry + timeout,
built in) — see its README's "Timeouts and retries" section.

## Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/check-token` | Verify if the provided token is valid |
| GET | `/home` | Welcome message |

### Artifact & Dataset Queries

A PHerc / Cornice / Pezzo is an **artifact**, reachable two ways on one
`/artifacts` resource: **by name** (query params) or **by UUID** (path). Names
match `displayName` **exactly** — resolve noisy input with `/resolve` first.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/artifacts` | List every artifact with an EduceLabID, one row per UUID, with per-type dataset counts and catalogue fields |
| GET | `/artifacts?pherc=&cornice=&pezzo=` | Full detail for one artifact by name (properties, metadata, `educelabids`, child counts) |
| GET | `/artifacts/{uuid}` | Resolve a UUID to its artifact (type, displayName, hierarchy, parent, location) |
| GET | `/pherc` | List every scroll (PHerc), one summary row each; drawer placeholders left out |
| GET | `/subdivisions?pherc=` | List all Cornici and Pezzi for a PHerc (each with `aliases` + `educelabids`) |
| GET | `/all-datasets?pherc=` | All datasets under a PHerc, grouped by artifact (chain-pooled, `belongs_to_uuid`) |
| GET | `/pherc/{pherc_id}/subdivisions` | Path form of `/subdivisions`, kept for existing clients; 404s on ids containing a slash |
| GET | `/pherc/{pherc_id}/all-datasets` | Path form of `/all-datasets`, kept for existing clients; 404s on ids containing a slash |
| GET | `/educelabid/{uuid}/datasets` | Datasets for a specific EduceLabID (chain-pooled, `belongs_to_uuid`) |
| PUT | `/datasets/{dataset_uuid}/released` | Release or withdraw one dataset by its own UUID (`release_writers` only) |
| GET | `/resolve` | Fuzzy-resolve a noisy displayName to ranked PHerc/Cornice/Pezzo candidates |

### Pipelines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipelines` | Get all pipelines with status summaries; `search`/`sort`/`dir`/`offset`/`limit` return one page |
| GET | `/pipelines/{pipeline_id}/stages` | Get all process stages for a pipeline (each stage includes `input_dataset_paths` / `output_dataset_path`) |
| POST | `/pipelines` | Create a new pipeline linked to an EduceLabID |
| POST | `/pipelines/{pipeline_id}/processes` | Create a process (PGS, SPEC, REG, WEB) within a pipeline |
| PUT | `/pipelines/{pipeline_id}/processes/{proc_type}/status` | Update process status (completed/failed) |
| DELETE | `/pipelines/{pipeline_id}` | Delete a pipeline, its processes, and output datasets |
| GET | `/pipelines/{pipeline_id}/confirmation` | Get full pipeline summary with all stages |

## Endpoint Details

### GET /artifacts (by name)

Returns full detail for one artifact (PHerc / Cornice / Pezzo), resolved by
**exact** `displayName`. `pherc` is always required; add `cornice` and/or
`pezzo` to address a subdivision. Returns the node's own properties, attached
metadata nodes, the `educelabids` assigned to it, and child counts. Datasets are
**not** included — use `/all-datasets` or `/educelabid/{uuid}/datasets`.

For noisy names, call `/resolve` first to get the canonical `displayName`.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pherc` | string | required | PHerc displayName (exact) |
| `cornice` | string | - | Cornice displayName (exact) |
| `pezzo` | string | - | Pezzo displayName (exact) |

**Example:**
```
GET /artifacts?pherc=1044
GET /artifacts?pherc=1044&cornice=6
```

**Response:**
```json
{
  "type": "Cornice",
  "displayName": "6",
  "aliases": ["6", "Cr. 6"],
  "educelabids": ["abc-123"],
  "metadata": { "CustodialInstitution": { "name": "..." } },
  "pezzi_count": 3
}
```

Returns `404` if no matching artifact exists; `422` if `cornice` or `pezzo` is
given without `pherc`. With no parameters at all, the list below is returned.

### Kind, method and label

Every artifact on `/artifacts` (by name, by UUID, and each list row and its
`artifacts` entries) and every node on `/subdivisions` carries four fields
derived from its names (`educelab.hercdb.naming`, #23). They're never stored,
and display names are unchanged:

- **`kind`**: `papyrus`, `cornice`, `scorza`, `pezzo`, `cassetto_piece` (a
  piece taken out of a cassetto, e.g. `571 / Cass. 31`), `whole_cassetto`,
  `tavoletta` or `frammenti`. It's `null` for a placeholder PHerc node
  itself. Terms are defined in `docs/glossary.md`.
- **`method`**: `Osloense`, `Fackelmann` or `null`, from the cornice name (a
  pezzo takes its cornice's).
- **`label`** / **`label_parts`**: a readable name and the same as a lineage,
  e.g. `"PHerc. 465, Cornice 1 (Fackelmann), Pezzo 465/2"`,
  `"Tavoletta A, Cassetto 29"`, `"Cassetto 51 (A)"`.

A few rules rest on open questions (Q-04, Q-09, Q-10, Q-19 in
`docs/open_questions.md`) and may change when those are answered.

### GET /artifacts (list)

With no parameters, lists every artifact that has an EduceLabID, one row per
UUID, ordered by PHerc / Cornice / Pezzo name:

```json
{
  "uuid": "338f86f5-f8cc-5606-8c99-a48541b6801d",
  "type": "Cornice", "displayName": "1",
  "pherc": "2", "cornice": "1", "pezzo": null,
  "parent": {"type": "PHerc", "displayName": "2"},
  "location": "PHerc2 Cornice 1",
  "artifacts": [{"type": "Cornice", "displayName": "1", "pherc": "2", "cornice": "1",
                 "pezzo": null, "parent": {"type": "PHerc", "displayName": "2"},
                 "location": "PHerc2 Cornice 1"}],
  "datasets": {
    "PGSRaw": {"count": 1, "complete": 1, "failed": 0, "released": 1, "newest_complete_version": null},
    "WebProcessed": {"count": 2, "complete": 1, "failed": 0, "released": 1, "newest_complete_version": "2.2.0"}
  },
  "catalogue": {"author": "Scriptor Graecus incertus", "work": null, "language": "grc"}
}
```

- **Identity** is what `/artifacts/{uuid}` returns. `artifacts` lists every
  artifact the UUID is assigned to; that is one, except for the few UUIDs shared
  by several artifacts, whose identity is the first entry (PHercs first, then by
  name; `/artifacts/{uuid}` picks the same one).
- **`datasets`** is keyed by dataset type, with absent types omitted, pooled
  across the REPLACES chain like the dataset reads. `complete` uses the
  `newest_completed` rule (strict file counts for raw scans, a finished Process
  for processed data); `failed` counts processed datasets whose Process failed;
  `released` counts datasets that are released *and* complete; and
  `newest_complete_version` is the pipeline version of the complete processed
  dataset with the latest end time (`null` for raw types or when unrecorded).
- **`tray`** is `{kind, method, label, papyri}` for the tray as a whole. Kind
  and method come from its most specific object. The label is that object's
  label, or, for a tray shared by several papyri, the tray's name and the
  papyri: `"Cornice 1 (Osloense): PHerc. 216, 219, 225"`. Placeholder trays
  (tavolette, whole cassetti, frammenti) are listed, with `papyri: []`.
- **`catalogue`** holds the PHerc's Author, `literary_work` and Language.

Artifacts with no EduceLabID can't hold datasets and aren't listed; use
`/pherc` or `/subdivisions` for them.

### GET /artifacts/{uuid} (by UUID)

Resolves a UUID to the physical artifact it is assigned to — the UUID → artifact
bridge. Lightweight: for full detail, look the artifact up by name.

**Example:**
```
GET /artifacts/85f7b1ea-e57a-5d98-b481-658d75ac2dcf
```

**Response:**
```json
{
  "uuid": "85f7b1ea-e57a-5d98-b481-658d75ac2dcf",
  "type": "Cornice",
  "displayName": "1",
  "pherc": "10",
  "cornice": "1",
  "pezzo": null,
  "parent": { "type": "PHerc", "displayName": "10" },
  "kind": "cornice",
  "method": null,
  "label": "PHerc. 10, Cornice 1",
  "label_parts": ["PHerc. 10", "Cornice 1"],
  "location": "PHerc10 Cornice 1"
}
```

Returns `404` if no artifact is found for the UUID.

### GET /pherc

Lists every scroll (PHerc), one row each, ordered by `displayName`:

```json
[
  {
    "displayName": "0101b",
    "literary_work": null,
    "unrolling_status": "Unrolled",
    "metadata": {
      "Author": {"name": "Scriptor Graecus incertus"},
      "Language": {"name": "grc", "url": "http://id.loc.gov/vocabulary/iso639-2/grc"}
    },
    "cornici_count": 0,
    "pezzi_count": 0
  }
]
```

`metadata` holds Author and Language as `/artifacts` gives them; a label is
absent when the scroll has none. The counts are direct Cornice / Pezzo children,
as on `/artifacts`. PHerc nodes that are drawer placeholders (`tavoletta`,
`Cassetto`, `frammenti`) are not scrolls and are left out. For one scroll's full
record use `/artifacts?pherc=`.

### GET /subdivisions?pherc=

Lists all Cornici and Pezzi for a PHerc, including Pezzi nested under Cornici.
Each node (the PHerc itself, every Cornice, every Pezzo) is returned as
`{displayName, aliases, educelabids, parent, kind, method, label, label_parts,
shared_with}` (see *Kind, method and label*). `shared_with` lists the objects
of *other* papyri on the same tray, as `{uuid, pherc, cornice, pezzo, label}`,
and is empty when the tray isn't shared. There are no other physical
characteristics.
`pherc` is required (422 if missing); 404 if no PHerc has that displayName.

The PHerc is a query parameter, as on `/artifacts`, because some ids contain a
slash (`1007/1673`). The older path form `/pherc/{pherc_id}/subdivisions` still
works for other ids but 404s on those, even URL-encoded.

**Example:**
```
GET /subdivisions?pherc=238
GET /subdivisions?pherc=1007%2F1673
```

**Response:**
```json
{
  "pherc": { "displayName": "238", "aliases": ["238"], "educelabids": [], "parent": null,
             "kind": "papyrus", "method": null, "label": "PHerc. 238", "label_parts": ["PHerc. 238"] },
  "cornici": [
    { "displayName": "Scorze da 238 a 239", "aliases": ["Scorza"], "educelabids": ["..."],
      "parent": { "type": "PHerc", "displayName": "238" },
      "kind": "scorza", "method": null, "label": "PHerc. 238, Scorze da 238 a 239",
      "label_parts": ["PHerc. 238", "Scorze da 238 a 239"] }
  ],
  "pezzi": [ "..." ]
}
```

### GET /all-datasets?pherc=

Returns all datasets under a PHerc umbrella, grouped by EduceLabID (physical
artifact). Traverses the full hierarchy: PHerc itself, its Cornici, and all
Pezzi. Datasets are pooled across each artifact's UUID-replacement (REPLACES)
chain and grouped by the active/assigned UUID; each dataset carries
`belongs_to_uuid` (the UUID it actually belongs to).

As with `/subdivisions`, the older path form `/pherc/{pherc_id}/all-datasets`
takes the same parameters but 404s on PHerc ids containing a slash.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pherc` | string | required | PHerc displayName (exact) |
| `dataset_type` | string | - | Filter by type: `FlatbedScan`, `PGSRaw`, or `SpectralRaw` |
| `newest_completed` | bool | false | Return only the newest completed dataset per type per artifact |
| `released_only` | bool | false | Return only released datasets (with `newest_completed`, the newest released one) |

**Example:**
```
GET /all-datasets?pherc=1044
GET /all-datasets?pherc=1044&dataset_type=PGSRaw&newest_completed=true
```

**Response:**
```json
{
  "pherc": "1044",
  "artifacts": [
    {
      "uuid": "abc-123",
      "artifact_name": "PHerc1044 Cornice 6",
      "pherc": "1044",
      "cornice": "6",
      "pezzo": null,
      "datasets": [
        {
          "type": "PGSRaw",
          "path": "Dailies/PGS/...",
          "complete": "True",
          "date_end": "2022-11-02T09:38:30.000000000+00:00",
          "belongs_to_uuid": "abc-123"
        }
      ]
    }
  ]
}
```

A PHerc with no datasets (or none matching the filters) returns `200` with
`"artifacts": []`; `404` means no PHerc has that displayName.

### GET /educelabid/{uuid}/datasets

Returns all datasets for a specific EduceLabID, pooled across the UUID's
replacement (REPLACES) chain. Each dataset carries `belongs_to_uuid` so a scan
sitting on a retired predecessor UUID is visible.

An EduceLabID with no datasets (or none matching the filters) returns `200 []`;
`404` means the uuid is not an EduceLabID.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dataset_type` | string | - | Filter by type: `FlatbedScan`, `PGSRaw`, or `SpectralRaw` |
| `newest_completed` | bool | false | Return only the newest completed dataset per type |
| `released_only` | bool | false | Return only released datasets |

**Example:**
```
GET /educelabid/abc-123/datasets
GET /educelabid/abc-123/datasets?dataset_type=SpectralRaw&newest_completed=true
```

**Response:**
```json
[
  {
    "type": "PGSRaw",
    "path": "Dailies/PGS/...",
    "complete": "True",
    "date_end": "2022-11-02T09:38:30.000000000+00:00",
    "released": true,
    "belongs_to_uuid": "abc-123"
  }
]
```

### PUT /datasets/{dataset_uuid}/released

Release (publish) or withdraw one dataset, by its own `uuid`: a raw scan's scan
UUID, or the UUID a pipeline minted for its output. Only token users listed in
`release_writers` (`HERCDB_RELEASE_WRITERS`, or a `release_writers` list in
`~/.educedb`) may call it.

**Request body:**
```json
{
  "released": false,
  "released_by": "reviewer-a"
}
```

`released_by` is optional and defaults to the token's user; pass it when acting
for someone else. Flatbed negatives are not releasable.

**Response (200):**
```json
{
  "type": "PGSRaw",
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "path": "Dailies/PGS/...",
  "released": false,
  "released_by": "reviewer-a",
  "released_at": "2026-10-01T14:00:00+00:00"
}
```

403 for a token not in `release_writers`, 404 for no such dataset, 409 (with
nothing written) when two datasets share the UUID.

New datasets start as `release_default` says (`HERCDB_RELEASE_DEFAULT`, or
`release_default` in `~/.educedb`; `true` when unset).

### GET /resolve

Fuzzy-resolve a noisy PHerc / Cornice / Pezzo `displayName` to a ranked list of candidates. Use this when you have an approximate name (typo, extra spaces, alternate spelling) and want to identify the right node before calling other endpoints.

Returns `200 []` when no candidate clears the threshold — this is a discovery endpoint, not a "fetch this thing" lookup.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | required | Approximate displayName to look up |
| `label` | string | `PHerc` | One of `PHerc`, `Cornice`, `Pezzo` |
| `parent_pherc` | string | - | Fuzzy parent PHerc scope (for Cornice/Pezzo lookups) |
| `parent_cornice` | string | - | Fuzzy parent Cornice scope (for Pezzo lookups) |
| `threshold` | int | `75` | Minimum similarity score 0–100 |
| `limit` | int | `10` | Maximum ranked candidates to return |

**Example:**
```
GET /resolve?name=118+a
GET /resolve?name=Cass&label=Cornice&parent_pherc=72
```

**Response:**
```json
[
  {
    "displayName": "118a",
    "score": 100,
    "node": { "displayName": "118a", ... },
    "parent_pherc": null,
    "parent_cornice": null
  }
]
```

Scores are computed with `rapidfuzz.fuzz.ratio` on whitespace-stripped, lowercased names. Exact matches (after normalization) short-circuit to score 100. Invalid `label` values return `400`.

### GET /pipelines

Returns all pipelines with their computed status summaries.

**Response:**
```json
[
  {
    "start_time": "2025-01-15T10:30:00",
    "dataset_name": "PHerc1044 Cornice 4",
    "artifact_uuid": "abc-123",
    "pipeline_id": "20251222-389",
    "status": "completed",
    "version": "2.2.0",
    "proc_types": ["PGS", "SPEC", "REG"]
  }
]
```

`start_time` is the latest stage start. `version` is `null` when the pipeline
recorded none. Possible status values: `completed`, `partially_completed`,
`running`, `archiving`, `failed`, `unknown(error)`.

**Paging.** Give any of these and the response becomes one page,
`{"rows": [...], "matched": 12, "total": 7353, "sort": "started", "dir": "desc"}`:

| Param | Meaning |
|-------|---------|
| `search` | Keep pipelines where `dataset_name`, `artifact_uuid`, `pipeline_id`, `proc_types`, `version` or `status` contains it, compared as folded words, so `PHerc6`, `pherc 6` and `PHerc. 6` are the same. A search ending in a space or punctuation must end on a word: `PHerc. 6,` skips PHerc 60. |
| `sort` | `started` (default), `type`, `version`, `artifact` (natural order on `dataset_name`) or `status`; anything else is a `422` |
| `dir` | `asc` or `desc`; defaults to newest-first for `started` and `version` (unversioned last), ascending otherwise |
| `offset`, `limit` | The slice of the sorted matches; no `limit` returns them all |

Ties break on `pipeline_id`, so consecutive pages never repeat or skip a row.
With no parameters the response is the plain list above, unchanged for
existing callers.

### GET /pipelines/{pipeline_id}/stages

Returns all process stages for a given pipeline, ordered by timestamp.

**Example:**
```
GET /pipelines/20251222-389/stages
```

**Response:**
```json
[
  {
    "datetime": "2025-01-15T10:00:00",
    "proc_type": "PGS",
    "status": "completed",
    "slurm_id": "12345",
    "input_dataset_paths": ["/data/raw/pgs/<uuid>"],
    "output_dataset_path": "/data/processed/pgs/<uuid>"
  }
]
```

`input_dataset_paths` is a list (a `REG` stage carries both its PGS and SPEC
inputs); `output_dataset_path` is a single path or `null`.

### POST /pipelines

Create a new pipeline linked to an EduceLabID.

**Request body:**
```json
{
  "pipeline_id": "20260312-001",
  "artifact_uuid": "abc-123",
  "datetime": "2026-03-12T10:00:00"
}
```

**Response (201):**
```json
{
  "pipeline_id": "20260312-001",
  "artifact_uuid": "abc-123",
  "datetime": "2026-03-12T10:00:00"
}
```

### POST /pipelines/{pipeline_id}/processes

Create a new process (stage) within a pipeline. Valid stages: `PGS`, `SPEC`, `REG`, `WEB`.

**Request body:**
```json
{
  "proc_type": "PGS",
  "input_dataset_paths": ["Dailies/PGS/..."],
  "output_dataset_path": "/processed/pgs/20260312-001",
  "slurm_id": "88001",
  "start_datetime": "2026-03-12T10:05:00"
}
```

An optional `"released": true|false` sets the output dataset's release flag;
omitted, the server's `release_default` applies. An optional
`"output_dataset_uuid"` records the UUID the pipeline minted for its output
(422 if it isn't a UUID).

**Response (201):**
```json
{
  "proc_type": "PGS",
  "slurm_id": "88001",
  "start_time": "2026-03-12T10:05:00",
  "status": "submitted"
}
```

### PUT /pipelines/{pipeline_id}/processes/{proc_type}/status

Update the status of a process. Valid statuses: `completed`, `failed`.

**Request body:**
```json
{
  "status": "completed",
  "end_datetime": "2026-03-12T11:00:00"
}
```

**Response:**
```json
{
  "proc_type": "PGS",
  "slurm_id": "88001",
  "start_time": "2026-03-12T10:05:00",
  "end_time": "2026-03-12T11:00:00",
  "status": "completed"
}
```

### DELETE /pipelines/{pipeline_id}

Delete a pipeline and all its processes and output dataset nodes. Input datasets (PGSRaw, SpectralRaw) are not deleted.

**Response:**
```json
{
  "pipeline_id": "20260312-001",
  "processes_deleted": 4,
  "output_datasets_deleted": 4
}
```

### GET /pipelines/{pipeline_id}/confirmation

Get a full pipeline summary including all stages.

**Response:**
```json
{
  "pipeline_id": "20260312-001",
  "artifact_uuid": "abc-123",
  "datetime": "2026-03-12T10:00:00",
  "status": "completed",
  "stages": [
    {
      "proc_type": "PGS",
      "slurm_id": "88001",
      "start_time": "2026-03-12T10:05:00",
      "end_time": "2026-03-12T11:00:00",
      "status": "completed"
    }
  ]
}
```
