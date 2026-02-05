# EduceLab Herculaneum Graph Database API

This API is considered a work in progress and can change at any moment.

## Installation

The latest release is available on PyPI:

```shell
python3 -m pip install educelab-hercdb
```

## Connect to a server

```python
from educelab import hercdb

uri = "neo4j://localhost:7687"
user = "foo"
password = "bar"
db = hercdb.connect(uri, user, password)
if db.verify_connection():
  print("Connected!")
```

### Server configuration

If not provided when calling `hercdb.connect()`, this package will attempt to 
read the URI, username, and password from the configuration file at `~/.educedb`. 
This file is expected to be in the [TOML](https://toml.io/) format:
```toml
[database]
uri = "neo4j://localhost:7687"
username = "foo"
password = "bar"
```
The section header is optional, and only the information from the first section 
will be read. In the future, sections may be used to differentiate multiple 
database servers. **Note: In Python 3.10, the configuration file is loaded 
using `configparser`, which does not support the full TOML syntax.**

Alternatively, the server information can be provided by exporting the following 
environment variables:
```shell
export EDUCEDB_URI='neo4j://localhost:7687'
export EDUCEDB_USER=foo
export EDUCEDB_PASSWORD=bar
```
Environment variables take priority over the configuration file. 

As a convenience, this package provides the `hercdb.config.request_required()`
method, which will check for configuration values in the environment and
the configuration file and prompt for any which have not been provided:
```
>>> hercdb.config.request_required()

Enter URI: neo4j://localhost:7687
Enter username: foo
Enter password:
```

## Loading Data

Data loading is done in two steps using the loader scripts. Both read CSV files from `input_data/`.

### 1. Load metadata and UUIDs

```shell
uv run python src/educelab/hercdb/loader/metadata_loader.py
```

Reads (defaults):
- `input_data/metadata_file.csv` - Pre-processed metadata file. (PHerc, Cornice, Pezzo, Disegni nodes and properties.)
- `input_data/uuid_file.csv` - Pre-processed uuid file. (all EduceLabID added)

Optional arguments:
```shell
uv run python src/educelab/hercdb/loader/metadata_loader.py \
  --metadata path/to/metadata.csv \
  --uuid path/to/uuid.csv
```

### 2. Load scan data

```shell
uv run python src/educelab/hercdb/loader/scan_loader.py
```

Reads (defaults):
- `input_data/negatives.csv` - FlatbedScanDataset nodes
- `input_data/photogrammetry-scans.csv` - PGSRaw nodes
- `input_data/spectral-scans.csv` - SpectralRaw nodes

Optional arguments:
```shell
uv run python src/educelab/hercdb/loader/scan_loader.py \
  --negatives path/to/negatives.csv \
  --photogrammetry path/to/pgs.csv \
  --spectral path/to/spectral.csv
```

**Note:** Run metadata_loader first since scan data links to EduceLabID nodes.

### Delete all data

To clear the database before reloading:

```python
from educelab.hercdb.loader import PhercGraphDatabaseLoader
loader = PhercGraphDatabaseLoader()
loader._delete_all_nodes()
```