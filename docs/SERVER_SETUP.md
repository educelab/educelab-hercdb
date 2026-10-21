# Server Setup Guide

How to get the hercdb REST API running on a fresh server (VM or bare metal).
This assumes Neo4j is already installed and running.

## Prerequisites

- Python 3.10+ installed
- [uv](https://docs.astral.sh/uv/) installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Neo4j running and accessible (note the URI, username, and password)

## 1. Create the server's venv

The server runs one released version from PyPI, installed into its own venv,
not from a git checkout. That way the version it reports (`/openapi.json`,
`/docs`) is always a tag you can look up, and so is the client that
acquisition-workflow installs from PyPI.

```bash
uv venv ~/hercdb-server
```

## 2. Install a release

Install an exact version with the server extra (FastAPI, Neo4j driver, uvicorn, etc.):

```bash
uv pip install --python ~/hercdb-server "educelab-hercdb[server]==0.3.10"
```

Later versions go in with `scripts/deploy_server.sh` (see
[Deploying a release](#deploying-a-release)). A git checkout isn't needed on the
server. Migrations, loaders and the admin CLIs can be run from any machine that
reaches Neo4j.

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
~/hercdb-server/bin/python -c "
from educelab.hercdb.db import connect
db = connect()
print('Connected!' if db.verify_connection() else 'Failed')
"
```

## 6. Start the REST API

### Development (from a checkout, with auto-reload)

On a development machine, not the production server:

```bash
uv sync --extra server
uv run uvicorn educelab.hercdb.rest.server:app --host 0.0.0.0 --port 8000 --reload
```

Once running, check the interactive docs at `http://<server-ip>:8000/docs`.

### Production (systemd service)

1. Copy the provided service file ([`src/educelab/hercdb/rest/hercdb.service`](../src/educelab/hercdb/rest/hercdb.service)
   in the repo, or save it from GitHub):

   ```bash
   sudo cp hercdb.service /etc/systemd/system/hercdb.service
   ```

2. Edit it to match your setup:

   ```bash
   sudo nano /etc/systemd/system/hercdb.service
   ```

   Update these fields:
   ```ini
   [Service]
   User=your_username
   WorkingDirectory=/home/your_username
   ExecStart=/home/your_username/hercdb-server/bin/uvicorn educelab.hercdb.rest.server:app --host 0.0.0.0 --port 8000
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

## Deploying a release

Every deploy installs an exact version that is already on PyPI. Install the
script once (from a checkout, or saved from GitHub):

```bash
sudo install -m 755 scripts/deploy_server.sh /usr/local/sbin/hercdb_deploy
```

Then, as the service user:

```bash
hercdb_deploy 0.3.10
```

The script:
1. installs `educelab-hercdb[server]==0.3.10` into `~/hercdb-server`;
2. restarts `hercdb`;
3. waits until `/openapi.json` reports `0.3.10`;
4. prints the rollback command, which is the same command with the previous version.

`VENV`, `SERVICE`, `URL` and `WAIT_SECONDS` override the defaults.

**Release order.** acquisition-workflow installs the client from PyPI with a
range (`>=0.3.9,<0.4`), so a new client reaches the cluster as soon as it is
published, whether or not the server has it. Keep the two in step:

1. Merge to `develop`, then tag `vX.Y.Z` and push the tag. PyPI publishes automatically.
2. Run `hercdb_deploy X.Y.Z` on the server the same day.
3. Add an entry to [deploy_log.md](deploy_log.md).
4. Only then update consumers that need the new endpoints. Anything that breaks
   an existing client waits for 0.4.0.

### Switching a server that runs from a git checkout

1. Create the venv and install the running release (steps 1–2 above). The
   checkout keeps serving meanwhile.
2. Point `ExecStart` and `WorkingDirectory` in `/etc/systemd/system/hercdb.service` at the venv (step 6),
   then run `sudo systemctl daemon-reload && sudo systemctl restart hercdb`.
3. Check: `curl -s http://localhost:8000/openapi.json | python3 -c "import json,sys;print(json.load(sys.stdin)['info']['version'])"`.
   To go back, restore the old `ExecStart` and restart.
4. Once the server is verified, remove the checkout.

## Quick reference

| File | Purpose |
|------|---------|
| `~/.educedb` | Neo4j connection credentials (server-side) |
| `~/.tokens` | API Bearer tokens (server-side) |
| `~/hercdb-server/` | The venv the service runs from, holding one PyPI release |
| `src/educelab/hercdb/rest/hercdb.service` | systemd service template |
| `scripts/deploy_server.sh` | Deploy or roll back one exact version (installed as `hercdb_deploy`) |

See [AUTHENTICATION.md](AUTHENTICATION.md) for a deeper explanation of how the two auth layers relate.
