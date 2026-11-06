# Authentication & Secrets Overview

This project has two independent authentication layers.

## 1. Neo4j Database Credentials (server-side only)

Used by the REST API server and any scripts that connect to Neo4j directly.

| Source | Location | Priority |
|--------|----------|----------|
| Environment variables | `EDUCEDB_URI`, `EDUCEDB_USER`, `EDUCEDB_PASSWORD` | Highest |
| Config file | `~/.educedb` (TOML format) | Medium |
| Interactive prompt | `hercdb.config.request_required()` | Fallback |

Example `~/.educedb`:
```toml
[database]
uri = "neo4j://localhost:7687"
username = "neo4j"
password = "your_password"
```

The Neo4j settings are read from the first section, whatever its name
(`[database]` or `[hercdb]`). `[release]` holds the release settings (below);
any other section is ignored with a warning.

Managed in: `src/educelab/hercdb/config.py`

## 2. REST API Bearer Tokens (client-facing)

Used by any client calling the REST API (including `HercClient`).

### Server side

Tokens are stored in `~/.tokens` on the machine running the REST server. Each line maps a username to a token:
```
username1 = some-token-string
username2 = another-token-string
```

The server loads this file at startup. If the file is missing, no authentication will work.

Managed in: `src/educelab/hercdb/rest/server.py` (lines 16–27)

### Release writers

A valid token can read everything and record pipelines, but only the token
users named as **release writers** may release (publish) or withdraw a dataset
(`PUT /datasets/{uuid}/released`). Name them by their `~/.tokens` user name,
under `[release]` in `~/.educedb` or in `HERCDB_RELEASE_WRITERS`
(comma-separated), which wins over the file:

```toml
[release]
writers = ["portal"]
default = true           # whether a new dataset starts released (default true)
```

With no writers set, every release request gets a 403. The server reads the
list at startup, so restart it after a change. To check a token, send a
release request for a UUID that doesn't exist: `404` means its user is a
writer, `403` means it isn't, and nothing is written either way. Full steps
are in [SERVER_SETUP.md](SERVER_SETUP.md#release-settings).

### Client side

Pass the token when constructing a client. It is sent as a `Bearer` token in the `Authorization` header on every request:
```python
client = HercClient(host="api.example.com", token="some-token-string")
client.check_token()  # returns user info if valid, 401 otherwise
```

## How the two layers relate

```
Client (HercClient / curl / browser)
  │
  │  Bearer token (from ~/.tokens on server)
  ▼
REST API Server (FastAPI)
  │
  │  Neo4j credentials (from ~/.educedb or env vars)
  ▼
Neo4j Database
```

A client never sees the Neo4j password. The Neo4j database knows nothing about API tokens. The REST server bridges both: it authenticates clients via tokens, then uses the Neo4j credentials to run queries.

## Summary

| Layer | Secret | Stored at | Used by |
|-------|--------|-----------|---------|
| Database | Neo4j URI, user, password | `~/.educedb` or env vars | REST server, direct DB scripts |
| API | Bearer tokens | `~/.tokens` (server-side) | REST clients via HTTP header |
| API | Release writers (token user names, not secrets) | `[release]` in `~/.educedb` or `HERCDB_RELEASE_WRITERS` | REST server, for `PUT /datasets/{uuid}/released` |
