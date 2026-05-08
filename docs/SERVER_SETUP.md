# Server Setup Guide

How to get the hercdb REST API running on a fresh server (VM or bare metal).
This assumes Neo4j is already installed and running.

## Prerequisites

- Python 3.10+ installed
- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Neo4j running and accessible (note the URI, username, and password)

## 1. Clone the repository

```bash
git clone <repo-url> ~/educelab-hercdb
cd ~/educelab-hercdb
```

## 2. Install dependencies

Install with the server extra (includes FastAPI, Neo4j driver, uvicorn, etc.):

```bash
uv sync --extra server --no-dev
```

## 3. Configure Neo4j credentials

Create the config file at `~/.educedb`:

```bash
cat > ~/.educedb << 'EOF'
[database]
uri = "neo4j://localhost:7687"
username = "neo4j"
password = "your_password_here"
EOF
chmod 600 ~/.educedb
```

Replace the URI, username, and password with your actual Neo4j connection details.

Alternatively, use environment variables (these take priority over the config file):

```bash
export EDUCEDB_URI='neo4j://localhost:7687'
export EDUCEDB_USER=neo4j
export EDUCEDB_PASSWORD=your_password_here
```

## 4. Set up API tokens

The REST API uses Bearer token authentication. Create a `~/.tokens` file on the server with one `username = token` pair per line:

```bash
cat > ~/.tokens << 'EOF'
alice = some-random-token-string
bob = another-random-token-string
EOF
chmod 600 ~/.tokens
```

Generate tokens however you like (e.g., `python -c "import secrets; print(secrets.token_hex(32))"`).

Clients will use these tokens in the `Authorization: Bearer <token>` header.

## 5. Verify the connection

Quick sanity check that credentials work:

```bash
uv run python -c "
from educelab.hercdb.db import connect
db = connect()
print('Connected!' if db.verify_connection() else 'Failed')
"
```

## 6. Start the REST API

### Development (with auto-reload)

```bash
uv run uvicorn educelab.hercdb.rest.server:app --host 0.0.0.0 --port 8000 --reload
```

Once running, check the interactive docs at `http://<server-ip>:8000/docs`.

### Production (systemd service)

1. Copy the provided service file:

   ```bash
   sudo cp src/educelab/hercdb/rest/hercdb.service /etc/systemd/system/hercdb.service
   ```

2. Edit it to match your setup:

   ```bash
   sudo nano /etc/systemd/system/hercdb.service
   ```

   Update these fields:
   ```ini
   [Service]
   User=your_username
   WorkingDirectory=/home/your_username/educelab-hercdb
   ExecStart=/home/your_username/educelab-hercdb/.venv/bin/uvicorn educelab.hercdb.rest.server:app --host 0.0.0.0 --port 8000
   ```

   If you prefer environment variables over `~/.educedb`, add them here:
   ```ini
   Environment=EDUCEDB_URI=neo4j://localhost:7687
   Environment=EDUCEDB_USER=neo4j
   Environment=EDUCEDB_PASSWORD=your_password_here
   ```

3. Enable and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable hercdb    # start on boot
   sudo systemctl start hercdb     # start now
   ```

4. Check status and logs:

   ```bash
   sudo systemctl status hercdb
   journalctl -u hercdb -f
   ```

## 7. Test from a client

From any machine with network access to the server:

```bash
curl -H "Authorization: Bearer some-random-token-string" http://<server-ip>:8000/check-token
```

Or with the Python client:

```python
from educelab.hercdb.client import HercClient

client = HercClient(host="<server-ip>", token="some-random-token-string")
print(client.check_token())
```

## Quick reference

| File | Purpose |
|------|---------|
| `~/.educedb` | Neo4j connection credentials (server-side) |
| `~/.tokens` | API Bearer tokens (server-side) |
| `src/educelab/hercdb/rest/hercdb.service` | systemd service template |

See [AUTHENTICATION.md](AUTHENTICATION.md) for a deeper explanation of how the two auth layers relate.
