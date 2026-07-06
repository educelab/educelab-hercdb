# Server Setup (VM + systemd)

How to get the HercDB REST API running on a fresh server (VM or bare metal) as a
managed service. Assumes Neo4j is already installed and running.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Neo4j running and reachable (note the URI, username, password)

## 1. Clone and install

```bash
git clone <repo-url> ~/educelab-hercdb
cd ~/educelab-hercdb
git checkout v0.2.2            # or the version you intend to run
uv sync --extra server --no-dev   # FastAPI + uvicorn + Neo4j driver
```

> hercdb is **not on PyPI** — it is distributed via git tags. Check out the tag
> you want before installing.

## 2. Neo4j credentials — `~/.educedb`

TOML, with a `[database]` section and quoted values:

```bash
cat > ~/.educedb << 'EOF'
[database]
uri = "neo4j://localhost:7687"
username = "neo4j"
password = "your_password_here"
EOF
chmod 600 ~/.educedb
```

Environment variables override the file: `EDUCEDB_URI`, `EDUCEDB_USER`,
`EDUCEDB_PASSWORD`.

## 3. API tokens — `~/.tokens`

The REST API uses Bearer-token auth. One `name = token` pair per line:

```bash
cat > ~/.tokens << 'EOF'
alice = some-random-token-string
bob   = another-random-token-string
EOF
chmod 600 ~/.tokens
```

Generate tokens with `python -c "import secrets; print(secrets.token_hex(32))"`.
Clients send the token as `Authorization: Bearer <token>`.

## 4. Verify the connection

```bash
uv run python -c "from educelab.hercdb.db import connect; print('OK' if connect().verify_connection() else 'FAIL')"
```

## 5. Run as a systemd service (production)

1. Install the provided unit file:

   ```bash
   sudo cp src/educelab/hercdb/rest/hercdb.service /etc/systemd/system/hercdb.service
   ```

2. Edit it for your host (`sudo nano /etc/systemd/system/hercdb.service`):

   ```ini
   [Unit]
   Description=HercDB REST API
   After=network.target

   [Service]
   User=your_user
   WorkingDirectory=/home/your_user/educelab-hercdb
   ExecStart=/home/your_user/educelab-hercdb/.venv/bin/uvicorn educelab.hercdb.rest.server:app --host 0.0.0.0 --port 8000
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```

   `--host 0.0.0.0` is required so remote clients (e.g. an HPC login node) can
   reach it; the default binds to localhost only. If you prefer env vars over
   `~/.educedb`, add `Environment=EDUCEDB_URI=...` lines here.

3. Enable and start:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable hercdb    # start on boot
   sudo systemctl start hercdb     # start now
   sudo systemctl status hercdb
   journalctl -u hercdb -f         # follow logs
   ```

### Development alternative (no service)

```bash
uv run uvicorn educelab.hercdb.rest.server:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs are then at `http://<server-ip>:8000/docs`.

## 6. Test from a client

```bash
curl -H "Authorization: Bearer some-random-token-string" http://<server-ip>:8000/check-token
# -> {"valid": true, "user": "...", ...}
```

Or with the Python client:

```python
from educelab.hercdb.client import HercClient
client = HercClient(host="<server-ip>", token="some-random-token-string")
print(client.check_token())
```

If a remote client cannot reach the port, the server firewall likely blocks it —
open it, or use an SSH tunnel (`ssh -N -L 8000:localhost:8000 user@vm-host`).

## Quick reference

| File | Purpose |
|------|---------|
| `~/.educedb` | Neo4j connection credentials (server-side) |
| `~/.tokens` | API Bearer tokens (server-side) |
| `src/educelab/hercdb/rest/hercdb.service` | systemd unit template |
