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

For full server setup (credentials, tokens, systemd), see [docs/SERVER_SETUP.md](../../../docs/SERVER_SETUP.md).

## Authentication

All endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <token>
```

Tokens are loaded from `~/.tokens`. Each line has the format `username = token`.

## Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/check-token` | Verify if the provided token is valid |

### PHerc Queries

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pherc/{pherc_id}` | Get a PHerc and all directly attached nodes |
| GET | `/pherc/{pherc_id}/subdivisions` | List all Cornici and Pezzi for a PHerc |
| GET | `/pherc/{pherc_id}/cornice/{cornice_id}` | Get a specific Cornice and its attached nodes |
| GET | `/pherc/{pherc_id}/cornice/{cornice_id}/pezzo/{pezzo_id}` | Get a Pezzo under a specific Cornice |
| GET | `/pherc/{pherc_id}/pezzo/{pezzo_id}` | Get a Pezzo directly under a PHerc |
| GET | `/pherc/{pherc_id}/datasets/{dataset_type}` | Get imaging datasets for a PHerc |
| GET | `/pherc/{pherc_id}/all-datasets` | Get all datasets under a PHerc, grouped by artifact |
| GET | `/pherc/{pherc_id}/educelabids` | List all EduceLabIDs under a PHerc |
| GET | `/artifacts/{uuid}` | Get display name for an artifact by UUID |
| GET | `/educelabid/{uuid}/datasets` | Get datasets for a specific EduceLabID |
| POST | `/search` | Search for PHercs using multiple criteria |

### Pipelines

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipelines` | Get all pipelines with status summaries |
| GET | `/pipelines/{pipeline_id}/stages` | Get all process stages for a pipeline |
| POST | `/pipelines` | Create a new pipeline linked to an EduceLabID |
| POST | `/pipelines/{pipeline_id}/processes` | Create a process (PGS, SPEC, REG, WEB) within a pipeline |
| PUT | `/pipelines/{pipeline_id}/processes/{proc_type}/status` | Update process status (completed/failed) |
| DELETE | `/pipelines/{pipeline_id}` | Delete a pipeline, its processes, and output datasets |
| GET | `/pipelines/{pipeline_id}/confirmation` | Get full pipeline summary with all stages |

## Endpoint Details

### GET /pherc/{pherc_id}

Returns a PHerc and all its directly attached nodes (metadata, Cornici, direct Pezzi, etc.).

**Example:**
```
GET /pherc/211
```

### GET /pherc/{pherc_id}/subdivisions

Lists all Cornici and Pezzi for a PHerc, including Pezzi nested under Cornici. Returns only `name` and `displayName` for each subdivision.

**Example:**
```
GET /pherc/238/subdivisions
```

**Response:**
```json
{
  "pherc": { "displayName": "238", ... },
  "cornici": [
    { "name": "Scorza", "displayName": "Scorze da 238 a 239" }
  ],
  "pezzi": [
    { "name": null, "displayName": "1 (238a)" },
    { "name": null, "displayName": "2 (238b)" }
  ]
}
```

### GET /pherc/{pherc_id}/datasets/{dataset_type}

Returns imaging datasets for a PHerc. The `dataset_type` path parameter must be one of: `FlatbedScan`, `PGSRaw`, `SpectralRaw`.

**Query parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cornice` | string | - | Filter by Cornice display name |
| `pezzo` | string | - | Filter by Pezzo display name |
| `newest_completed` | bool | false | Return only the newest completed dataset |

**Example:**
```
GET /pherc/1044/datasets/SpectralRaw?cornice=4
```

**Response:**
```json
[
  {
    "path": "Dailies/Spectral/MVDaily_20221102/PHerc1044Cr04",
    "date_start": "2022-11-02T09:37:25.000000000+00:00",
    "date_end": "2022-11-02T09:38:30.000000000+00:00",
    "complete": "True",
    "uuid": "331cf7c0-631c-41cd-9be4-fa6fbd6b1288"
  }
]
```

### GET /pherc/{pherc_id}/all-datasets

Returns all datasets under a PHerc umbrella, grouped by EduceLabID (physical artifact). Traverses the full hierarchy: PHerc itself, its Cornici, and all Pezzi.

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
          "date_end": "2022-11-02T09:38:30.000000000+00:00"
        }
      ]
    }
  ]
}
```

### GET /pherc/{pherc_id}/educelabids

Lists all EduceLabIDs assigned to artifacts under a PHerc umbrella.

**Example:**
```
GET /pherc/1044/educelabids
```

**Response:**
```json
[
  {
    "uuid": "abc-123",
    "pherc": "1044",
    "cornice": "6",
    "pezzo": null,
    "artifact_name": "PHerc1044 Cornice 6"
  }
]
```

### GET /artifacts/{uuid}

Returns the display name of a physical artifact (PHerc, Cornice, Pezzo) for the given UUID.

**Example:**
```
GET /artifacts/85f7b1ea-e57a-5d98-b481-658d75ac2dcf
```

**Response:**
```json
{
  "display_name": "PHerc10 Cornice 1"
}
```

Returns `404` if no artifact is found for the UUID.

---

### GET /educelabid/{uuid}/datasets

Returns all datasets for a specific EduceLabID.

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
    "date_end": "2022-11-02T09:38:30.000000000+00:00"
  }
]
```

### POST /search

Search for PHercs using multiple criteria. All provided filters are intersected (AND logic). Returns a list of matching PHerc display names.

**Request body (all fields optional):**
```json
{
  "uuid": "",
  "display-name": "",
  "author": "",
  "language": "",
  "unrolling-status": "",
  "scorze": "",
  "unrolling-method": "",
  "unroller": "",
  "literary-work": "",
  "editions": "",
  "subscriptio": "",
  "instituion": "",
  "initial-end-title": "",
  "recto-verso-title": "",
  "multiple-hands": "",
  "neapolitan-drawings": "",
  "oxonian-drawings": "",
  "cavallo-scribal-style": "",
  "diameter_operator": "",
  "diameter_value": "",
  "height_operator": "",
  "height_value": "",
  "width_operator": "",
  "width_value": "",
  "weight_operator": "",
  "weight_value": "",
  "unrolled_year_operator": "",
  "unrolled_year_value": ""
}
```

For `editions`, `literary-work`, `neapolitan-drawings`, and `oxonian-drawings`, use the value `"ALL"` to match any PHerc that has that property set.

Numeric operators (`diameter_operator`, etc.) accept: `=`, `<=`, `>=`.

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
    "slurm_id": "12345"
  }
]
```

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
