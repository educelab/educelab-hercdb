# HercClient

Lightweight Python client for the EduceLab HercDB REST API. Only depends on `requests` — no Neo4j, FastAPI, or other server-side dependencies required.

## Installation

```shell
pip install educelab-hercdb
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
| `search(**criteria)` | For the Database Web GUI -- Search for PHercs using multiple criteria (AND logic). |

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
