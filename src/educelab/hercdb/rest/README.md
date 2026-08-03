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

### Artifact & Dataset Queries

A PHerc / Cornice / Pezzo is an **artifact**, reachable two ways on one
`/artifacts` resource: **by name** (query params) or **by UUID** (path). Names
match `displayName` **exactly** — resolve noisy input with `/resolve` first.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/artifacts?pherc=&cornice=&pezzo=` | Full detail for one artifact by name (properties, metadata, `educelabids`, child counts) |
| GET | `/artifacts/{uuid}` | Resolve a UUID to its artifact (type, displayName, hierarchy, parent, location) |
| GET | `/pherc/{pherc_id}/subdivisions` | List all Cornici and Pezzi for a PHerc (each with `aliases` + `educelabids`) |
| GET | `/pherc/{pherc_id}/all-datasets` | All datasets under a PHerc, grouped by artifact (chain-pooled, `belongs_to_uuid`) |
| GET | `/educelabid/{uuid}/datasets` | Datasets for a specific EduceLabID (chain-pooled, `belongs_to_uuid`) |
| GET | `/resolve` | Fuzzy-resolve a noisy displayName to ranked PHerc/Cornice/Pezzo candidates |

### Pipelines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipelines` | Get all pipelines with status summaries |
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

Returns `404` if no matching artifact exists; `422` if `pherc` is omitted.

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
  "location": "PHerc10 Cornice 1"
}
```

Returns `404` if no artifact is found for the UUID.

### GET /pherc/{pherc_id}/subdivisions

Lists all Cornici and Pezzi for a PHerc, including Pezzi nested under Cornici.
Each node (the PHerc itself, every Cornice, every Pezzo) is returned as
`{displayName, aliases, educelabids}` — no other physical characteristics.

**Example:**
```
GET /pherc/238/subdivisions
```

**Response:**
```json
{
  "pherc": { "displayName": "238", "aliases": ["238"], "educelabids": [] },
  "cornici": [
    { "displayName": "Scorze da 238 a 239", "aliases": ["Scorza"], "educelabids": ["..."] }
  ],
  "pezzi": [
    { "displayName": "1 (238a)", "aliases": [], "educelabids": ["..."] }
  ]
}
```

### GET /pherc/{pherc_id}/all-datasets

Returns all datasets under a PHerc umbrella, grouped by EduceLabID (physical
artifact). Traverses the full hierarchy: PHerc itself, its Cornici, and all
Pezzi. Datasets are pooled across each artifact's UUID-replacement (REPLACES)
chain and grouped by the active/assigned UUID; each dataset carries
`belongs_to_uuid` (the UUID it actually belongs to).

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dataset_type` | string | - | Filter by type: `FlatbedScan`, `PGSRaw`, or `SpectralRaw` |
| `newest_completed` | bool | false | Return only the newest completed dataset per type per artifact |

**Example:**
```
GET /pherc/1044/all-datasets
GET /pherc/1044/all-datasets?dataset_type=PGSRaw&newest_completed=true
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

### GET /educelabid/{uuid}/datasets

Returns all datasets for a specific EduceLabID, pooled across the UUID's
replacement (REPLACES) chain. Each dataset carries `belongs_to_uuid` so a scan
sitting on a retired predecessor UUID is visible.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `dataset_type` | string | - | Filter by type: `FlatbedScan`, `PGSRaw`, or `SpectralRaw` |
| `newest_completed` | bool | false | Return only the newest completed dataset per type |

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
    "belongs_to_uuid": "abc-123"
  }
]
```

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
    "datetime": "2025-01-15T10:30:00",
    "dataset_name": "PHerc1044 Cornice 4",
    "artifact_uuid": "abc-123",
    "pipeline_id": "20251222-389",
    "status": "completed"
  }
]
```

Possible status values: `completed`, `partially_completed`, `running`, `failed`, `unknown(error)`.

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
