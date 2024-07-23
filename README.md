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
read the URI, username, and password from the configuration file at `~/.hercdb`. 
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