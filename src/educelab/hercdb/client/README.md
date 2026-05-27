# HercClient

Lightweight Python client for the EduceLab HercDB REST API. Only depends on `requests` — no Neo4j, FastAPI, or other server-side dependencies required.

## Installation

```shell
git clone https://github.com/educelab/hercdb.git
cd hercdb
uv sync --no-dev
source .venv/bin/activate
```

## Quick Start

```python
from educelab.hercdb.client import HercClient

client = HercClient(host="api.example.com", token="my-token")

# Verify your token
client.check_token()

# Get a PHerc and all its attached nodes
pherc = client.get_pherc("211")
```

## Constructor

```python
HercClient(host, token, port=8000, scheme="http")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | str | *(required)* | Hostname or IP of the API server |
| `token` | str | *(required)* | Bearer token for authentication |
| `port` | int | `8000` | Port number |
| `scheme` | str | `"http"` | URL scheme (`"http"` or `"https"`) |

## Methods

### Authentication

| Method | Description |
|--------|-------------|
| `check_token()` | Verify that the current token is valid. Returns user info. |
| `home()` | Call the welcome endpoint. |

### PHerc Queries

| Method | Description |
|--------|-------------|
| `get_pherc(pherc_id)` | Get a PHerc and all its directly attached nodes. |
| `get_cornice(pherc_id, cornice_id)` | Get a Cornice and its attached nodes. |
| `get_pezzo(pherc_id, pezzo_id, cornice_id=None)` | Get a Pezzo. If `cornice_id` is given, looks up the Pezzo under that Cornice. |
| `get_subdivisions(pherc_id)` | List all Cornici and Pezzi for a PHerc. |
| `get_datasets(pherc_id, dataset_type, ...)` | Get imaging datasets. `dataset_type` is one of `"FlatbedScan"`, `"PGSRaw"`, `"SpectralRaw"`. |
| `get_all_datasets_for_pherc(pherc_id, ...)` | Get all datasets under a PHerc, grouped by EduceLabID. |
| `get_educelabids_for_pherc(pherc_id)` | List all EduceLabIDs under a PHerc umbrella. |
| `get_artifact(uuid)` | Get the display name for an artifact by its UUID. |
| `get_datasets_for_educelabid(uuid, ...)` | Get all datasets for a specific EduceLabID. |
| `resolve(name, label="PHerc", parent_pherc=None, parent_cornice=None, threshold=75, limit=10)` | Fuzzy-resolve a noisy displayName to ranked PHerc / Cornice / Pezzo candidates. |
| `search(display_name_fuzzy=None, display_name_fuzzy_threshold=None, **criteria)` | For the Database Web GUI -- Search for PHercs using multiple criteria (AND logic). `display_name_fuzzy` enables fuzzy matching on the PHerc displayName. |

### Pipelines

| Method | Description |
|--------|-------------|
| `get_pipelines()` | Get all pipelines with status summaries. |
| `get_pipeline_stages(pipeline_id)` | Get all process stages for a pipeline. |
| `initialize_pipeline(pipeline_id, artifact_uuid, datetime)` | Create a new pipeline linked to an EduceLabID. |
| `initialize_process(pipeline_id, proc_type, input_dataset_paths, output_dataset_path, slurm_id, start_datetime)` | Create a process (PGS, SPEC, REG, WEB) within a pipeline. |
| `update_process_status(pipeline_id, proc_type, status, end_datetime)` | Update process status to completed or failed. |
| `delete_pipeline(pipeline_id)` | Delete a pipeline, its processes, and output datasets. |
| `get_pipeline_confirmation(pipeline_id)` | Get full pipeline summary with all stages. |

## Examples

### Get subdivisions for a PHerc

```python
subs = client.get_subdivisions("238")
for cornice in subs["cornici"]:
    print(cornice["displayName"])
```

### Get datasets

```python
datasets = client.get_datasets("1044", "SpectralRaw", cornice="4")
for ds in datasets:
    print(ds["path"], ds["complete"])

# Get only the newest completed dataset
newest = client.get_datasets("1044", "PGSRaw", newest_completed=True)
```

### Get all datasets under a PHerc

```python
result = client.get_all_datasets_for_pherc("1044")
for artifact in result["artifacts"]:
    print(f"{artifact['artifact_name']} ({artifact['uuid']})")
    for ds in artifact["datasets"]:
        print(f"  [{ds['type']}] {ds.get('path', '')}")

# Filter to only PGSRaw datasets
result = client.get_all_datasets_for_pherc("1044", dataset_type="PGSRaw")

# Get only the newest completed dataset per type per artifact
result = client.get_all_datasets_for_pherc("1044", newest_completed=True)
```

### Two-step approach (EduceLabIDs then datasets)

```python
eids = client.get_educelabids_for_pherc("1044")
for eid in eids:
    print(f"{eid['artifact_name']} ({eid['uuid']})")
    datasets = client.get_datasets_for_educelabid(eid["uuid"])
    for ds in datasets:
        print(f"  [{ds['type']}] {ds.get('path', '')}")
```

### Search with multiple criteria

```python
results = client.search(language="grc", author="Epicurus")
print(results["PHercs"])  # list of matching PHerc display names

# Fuzzy match on the PHerc displayName (handles noisy input like extra
# spaces, typos, alternate spellings). Intersects with every other
# criterion via the same AND logic.
results = client.search(display_name_fuzzy="118 a", language="grc")

# Loosen / tighten the similarity threshold (0-100, default 75 server-side):
results = client.search(display_name_fuzzy="4211", display_name_fuzzy_threshold=80)
```

### Fuzzy name lookup (resolve)

When you have a noisy name and want to find the right PHerc / Cornice /
Pezzo node, use `resolve()`. It returns ranked candidates so you can
either auto-pick the top hit or surface them as "did you mean…?" in a
UI. Once you've identified the node, use its UUID / EduceLabID with the
other client methods for everything else.

```python
# PHerc — "118 a" normalizes (whitespace-stripped + lowercased) to
# match "118a" exactly, so this short-circuits to a single score-100 hit.
matches = client.resolve("118 a")
for m in matches:
    print(m["displayName"], m["score"])

# Cornice — both the parent PHerc name and the cornice name itself are
# fuzzy. parent_pherc context comes back on each candidate.
matches = client.resolve("Cass", label="Cornice", parent_pherc="72")
for m in matches:
    print(m["displayName"], "under PHerc", m["parent_pherc"]["displayName"])

# Pezzo — optionally scope by both PHerc and Cornice parents.
matches = client.resolve(
    "1r", label="Pezzo",
    parent_pherc="238", parent_cornice="Scorze da 238 a 239",
)

# An empty list means "no candidate above threshold". Lower threshold
# or raise limit to widen the net.
maybe_more = client.resolve("4211", threshold=70, limit=20)
```

### Pipeline status

```python
pipelines = client.get_pipelines()
for p in pipelines:
    print(p["pipeline_id"], p["status"], p["dataset_name"])

stages = client.get_pipeline_stages("20251222-389")
for stage in stages:
    print(stage["proc_type"], stage["status"])
```

### Create and manage a pipeline

```python
from datetime import datetime

# Create a pipeline
result = client.initialize_pipeline("20260312-001", "abc-123", datetime.now().isoformat())

# Submit a PGS process
result = client.initialize_process(
    pipeline_id="20260312-001",
    proc_type="PGS",
    input_dataset_paths=["Dailies/PGS/..."],
    output_dataset_path="/processed/pgs/20260312-001",
    slurm_id="88001",
    start_datetime=datetime.now().isoformat(),
)

# Mark it completed
result = client.update_process_status("20260312-001", "PGS", "completed", datetime.now().isoformat())

# Get full pipeline confirmation
confirmation = client.get_pipeline_confirmation("20260312-001")
print(confirmation["status"])  # "completed" when all stages are done

# Delete pipeline and all its nodes (cleanup)
result = client.delete_pipeline("20260312-001")
print(f"Deleted {result['processes_deleted']} processes, {result['output_datasets_deleted']} output datasets")
```

## Error Handling

All methods raise `requests.HTTPError` on non-2xx responses. You can catch these to handle specific error cases:

```python
import requests

try:
    pherc = client.get_pherc("nonexistent")
except requests.HTTPError as e:
    if e.response.status_code == 404:
        print("PHerc not found")
    else:
        raise
```
