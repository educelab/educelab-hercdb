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
| `search(**criteria)` | Search for PHercs using multiple criteria (AND logic). |

### Pipelines

| Method | Description |
|--------|-------------|
| `get_pipelines()` | Get all pipelines with status summaries. |
| `get_pipeline_stages(pipeline_id)` | Get all process stages for a pipeline. |

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
    print(stage["stage"], stage["status"])
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
