# REST API & Client Reference

Every endpoint is protected by Bearer-token auth (`Authorization: Bearer
<token>`; tokens live in `~/.tokens` on the server). The Python client
(`HercClient`) wraps each one — only `requests` is required, no Neo4j or
server-side dependencies.

```python
from educelab.hercdb.client import HercClient
client = HercClient(host="vm-host", token="…", port=8000, scheme="http")
```

## Core concept: artifacts

A **PHerc / Cornice / Pezzo is an "artifact"**, addressed on the `/artifacts`
resource two ways:

- **By name** (query params) → full detail.
- **By UUID** (path) → a lightweight location bridge.

By-name fetches match `displayName` **exactly**. Resolve noisy input with
`/resolve` first — fuzzy matching lives only there.

## Read endpoints

| Method & path | Client method | Purpose |
|---|---|---|
| `GET /check-token` | `check_token()` | Verify the token; returns `{valid, user, …}`. |
| `GET /home` | `home()` | Welcome message. |
| `GET /artifacts?pherc=&cornice=&pezzo=` | `get_artifact_by_name(pherc, cornice=None, pezzo=None)` | Full detail for one artifact by exact name: own props, metadata, assigned `educelabids`, child counts. `pherc` required (missing → 422, not found → 404). No datasets. |
| `GET /artifacts/{uuid}` | `get_artifact(uuid)` | UUID → artifact bridge: `{uuid, type, displayName, pherc, cornice, pezzo, parent, location}`. |
| `GET /pherc/{id}/subdivisions` | `get_subdivisions(pherc_id)` | Full Cornici/Pezzi hierarchy. Each node `{displayName, aliases, educelabids, parent}`; `parent` is `{type, displayName}` (or `None` for the PHerc) so a nested Pezzo renders under its Cornice. |
| `GET /pherc/{id}/all-datasets` | `get_all_datasets_for_pherc(pherc_id, dataset_type=None, newest_completed=False)` | All datasets grouped by active/assigned EduceLabID, pooled across REPLACES chains; each dataset carries `belongs_to_uuid`. |
| `GET /educelabid/{uuid}/datasets` | `get_datasets_for_educelabid(uuid, dataset_type=None, newest_completed=False)` | Datasets for one UUID, pooled across its REPLACES chain; each carries `belongs_to_uuid`. |
| `GET /resolve` | `resolve(name, label="PHerc", parent_pherc=None, parent_cornice=None, threshold=75, limit=10)` | Fuzzy-resolve a noisy displayName to ranked candidates. Empty result is `200 []`, not 404. Invalid `label` → 400. |

`dataset_type` is one of `FlatbedScan`, `PGSRaw`, `SpectralRaw`.

### `/resolve` notes

Returns a JSON list ordered by `score` desc; exact matches (whitespace-stripped,
lowercased) score 100. Each item: `{displayName, name, score, nodeID,
parent_pherc, parent_cornice}`. Use it to turn a typo'd name into a real
artifact, then fetch by the resolved exact `displayName`.

## Pipeline endpoints

| Method & path | Client method | Purpose |
|---|---|---|
| `GET /pipelines` | `get_pipelines()` | All pipelines with status summaries. |
| `GET /pipelines/{id}/stages` | `get_pipeline_stages(id)` | All process stages for a pipeline. Each stage carries `input_dataset_paths` (list) and `output_dataset_path` (scalar, or null) alongside `proc_type`/`status`/`slurm_id`/`start_time`/`end_time`. A `REG` stage lists both its PGS and SPEC inputs. |
| `GET /pipelines/{id}/confirmation` | `get_pipeline_confirmation(id)` | Full summary with all stages. |
| `POST /pipelines` | `initialize_pipeline(pipeline_id, artifact_uuid, datetime)` | Create a Pipeline linked to an EduceLabID. |
| `POST /pipelines/{id}/processes` | `initialize_process(pipeline_id, proc_type, input_dataset_paths, output_dataset_path, slurm_id, start_datetime)` | Create a Process (stage) within a pipeline. |
| `PUT /pipelines/{id}/processes/{proc_type}/status` | `update_process_status(pipeline_id, proc_type, status, end_datetime)` | Set a process to `completed` / `failed`. |
| `DELETE /pipelines/{id}` | `delete_pipeline(id)` | Delete a Pipeline, its Process nodes, and their output datasets (raw/input datasets untouched). |

`proc_type` is one of `PGS`, `SPEC`, `REG`, `WEB`. **Process ordering matters
when creating:** `REG` matches the `PGSProcessed`/`SpectralProcessed` output
nodes that `PGS`/`SPEC` create, and `WEB` matches `REG`'s `Registered` node — so
record stages in order.

> **Naming note:** the REST/Python layer calls a process type `proc_type`, but
> the Neo4j `Process` node stores it under the property `stage`. The API
> translates between the two.

## Versioning & distribution

hercdb is published to **PyPI** on each release tag (`pip install educelab-hercdb`,
or pin a version, e.g. `educelab-hercdb==0.3.0`); a git-tag checkout still works
for local installs. Downstream consumers that depend on a specific API should
enforce the version at runtime — see the acquisition-workflow `_hercdb_compat.py`
guard pattern. Note its `SUPPORTED_HERCDB` range lives in that repo and must be
widened to admit `0.3.0` (the previous `">=0.2.2,<0.3"` excludes it).
