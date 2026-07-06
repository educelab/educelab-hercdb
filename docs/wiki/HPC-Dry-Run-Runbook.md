# HPC Pipeline Dry-Run Runbook

Verify that the acquisition-workflow `pipeline/submit_uber_pipeline.py` (branch
`pipeline-hercdb-0.2.1`) can talk to HercDB from an HPC login node, **without
submitting any SLURM jobs**, using the REST client backend (the default).

> A dry-run **does** write Pipeline/Process records to Neo4j (with placeholder
> slurm ids) so the write path is exercised end-to-end — no SLURM jobs run.
> Remove the test records afterward with `el-hercdb-pipeline-cleanup` on the VM
> (steps 10–11), or pass `--no-record-pipeline` to skip recording. See
> [Pipeline Recording & Cleanup](Pipeline-Recording-and-Cleanup).
>
> Because a dry-run submits no jobs, the per-stage **status updates**
> (`submitted` → `completed`/`failed`) don't happen here — those come from the
> stage scripts during a real run. How that works (and how to test it cheaply
> without a full run) is in
> [Pipeline Recording & Cleanup](Pipeline-Recording-and-Cleanup).

## Two machines, two environments (don't mix them)

| | Machine A — Neo4j VM | Machine B — HPC login node |
|---|---|---|
| Role | runs Neo4j + the REST **server** | runs the submit **script** (client) |
| Env manager | **uv** | **conda / Miniforge3** |
| Secrets | `~/.educedb` (Neo4j) + `~/.tokens` | `~/.hercdb_client.env` (token only) |
| Needs Neo4j password? | yes | **no** |

The client backend over HTTP needs only the **Bearer token + server host/port**;
the Neo4j credentials live only on the VM. The two machines never interact except
over HTTP. Python must be **3.10+** (hercdb requires it). Miniforge3 on the
cluster provides 3.11.

## Machine A — the Neo4j VM (REST server)

Stand up and run the REST server as described in
**[Server Setup (VM + systemd)](Server-Setup)**. You need a reachable host/port
(bind `--host 0.0.0.0`) and a Bearer token from `~/.tokens` — **copy that token;
the login node needs it.** The firewall must allow the login node to reach the
port (or use the SSH-tunnel fallback below).

## Machine B — the HPC login node (client)

### 1. Pull acquisition-workflow and check out the branch
```bash
git clone <acquisition-workflow-url> ~/acquisition-workflow
cd ~/acquisition-workflow
git checkout pipeline-hercdb-0.2.1
```

### 2. Create a conda env (Miniforge3) and install deps
This cluster's Python is conda-based, so use a conda env (**not** `python -m venv`).
```bash
module load ccs/Miniforge3
conda create -n $SCRATCH/hercdb-pipeline python=3.11 -y
source activate
conda activate hercdb-pipeline
python -m pip install -U pip setuptools wheel
```
Return later with `module load ccs/Miniforge3 && conda activate hercdb-pipeline`.

`educelab-hercdb` is **not on PyPI** (distributed via git tags), so install the
EduceLab packages **first**, then the requirements file — pip sees the pin
already satisfied and only fetches public deps. The login node needs only the
**client**, so a plain `pip install` is enough (no `--extra server`).
```bash
# educelab-hercdb at v0.2.2 — from a local clone checked out at the tag:
( cd ../educelab-hercdb && git fetch --tags && git checkout v0.2.2 )
pip install ../educelab-hercdb         # or: pip install "git+<hercdb-repo-url>@v0.2.2"
python -c "import importlib.metadata as m; print(m.version('educelab-hercdb'))"  # -> 0.2.2

pip install educelab-hpc               # however you normally install it
pip install -r requirements_pipeline.txt
```

### 3. Client credentials — `~/.hercdb_client.env` (no Neo4j password)
```bash
cat > ~/.hercdb_client.env << 'EOF'
export HERCDB_HOST=<vm-hostname-or-ip>
export HERCDB_PORT=8000
export HERCDB_SCHEME=http
export HERCDB_TOKEN=<the-token-from-the-VM>
EOF
chmod 600 ~/.hercdb_client.env
source ~/.hercdb_client.env
```

### 4. Pre-flight: confirm reachability + token
```bash
curl -s -H "Authorization: Bearer $HERCDB_TOKEN" \
  "$HERCDB_SCHEME://$HERCDB_HOST:$HERCDB_PORT/check-token"
# expect: {"valid":true,...}
```

### 5. Run the submit script — interactive, dry-run
Must be run **from the `pipeline/` directory** (the script does
`sys.path.append(os.getcwd())` to import its siblings).
```bash
cd ~/acquisition-workflow/pipeline
python3 submit_uber_pipeline.py --dry-run
```
The client backend is the default and the `HERCDB_*` env vars are picked up
automatically (or pass `--host/--port/--token`). Use `--backend direct` only when
running on the VM itself with Neo4j credentials.

You'll exercise: connectivity check → enter a P.Herc. number → tray list (incl.
the fuzzy fallback if you mistype, e.g. `137a` → offers `0137a`) → PGS/Spectral
dataset selection → pipeline naming → a printed "would-submit" job plan with no
`sbatch` calls → `Recorded pipeline <uber_job_id> (N process(es)).` for each
selected tray. **Note those `uber_job_id`s for cleanup.**

## Verify the written records, then clean up (on the VM)

The admin tool talks straight to Neo4j (no REST server needed). From the hercdb
checkout on the VM:

### 6. Verify
```bash
cd ~/educelab-hercdb
uv run el-hercdb-pipeline-cleanup --list        # lists every pipeline + its artifact
# or inspect one over REST from anywhere:
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://<vm-host>:8000/pipelines/<uber_job_id>/confirmation"
```

### 7. Clean up the test records
```bash
uv run el-hercdb-pipeline-cleanup <uber_job_id> [<uber_job_id> ...]   # -y to skip confirm
```
Deletes the Pipeline node, its Process nodes, and the output dataset nodes they
produced. Raw/input datasets (PGSRaw/SpectralRaw) are left untouched.

## What `--dry-run` guarantees (why no jobs run)

- **Globus login is skipped** (`tx.login` is behind `if not args.dry_run`).
- **Every `sbatch` is skipped** — jobs are printed, not submitted.
- **No log/shared dirs are created.**

The live external interactions are the HercDB read calls (selection) **and** the
HercDB write calls that record the pipeline — exactly what's being tested. The
version guard (`check_hercdb_version`) runs at startup, so a wrong hercdb version
on the login node fails loudly.

## Troubleshooting

### Login node can't reach the VM port (firewall)
Open an SSH tunnel from the login node, then point the client at localhost:
```bash
ssh -N -L 8000:localhost:8000 <user>@<vm-host> &
export HERCDB_HOST=localhost HERCDB_PORT=8000
```
Re-run the pre-flight `curl` and the script.

### `ModuleNotFoundError: globus_sdk.experimental.globus_app`
`globus_login.py` imports `globus_sdk.experimental.globus_app`, which globus-sdk
**removed in 3.50** (GlobusApp graduated out of `experimental`).
`requirements_pipeline.txt` pins only `globus-sdk>=3.42`, so a fresh install can
grab a too-new version; the import runs at module load, so it fails **even in
`--dry-run`**. Fix:
```bash
pip install "globus-sdk>=3.42,<3.50"
```

### `Permission denied (publickey)` on git over SSH (HPC node)
The node needs its own SSH key registered with GitLab. For a non-default key
name, point SSH at it via `~/.ssh/config`:
```
Host gitlab.com
    HostName gitlab.com
    User git
    IdentityFile ~/.ssh/id_ed25519_educelab
    IdentitiesOnly yes
```
Test with `ssh -T git@gitlab.com`.

## Quick reference

| File | Machine | Purpose |
|------|---------|---------|
| `~/.educedb` | VM | Neo4j connection creds (TOML, `[database]`) |
| `~/.tokens` | VM | API Bearer tokens (`name = token` per line) |
| `~/.hercdb_client.env` | login node | `HERCDB_HOST/PORT/SCHEME/TOKEN` (token only) |

CLI flags (override the `HERCDB_*` env vars): `--backend {client,direct}`
(default `client`), `--host`, `--port` (default 8000), `--scheme` (default
`http`), `--token`, `--dry-run`/`-n`, `--record-pipeline`/`--no-record-pipeline`.

REST endpoints the script hits (all Bearer-protected):
- read (GET): `/check-token`, `/pherc/{id}/subdivisions`,
  `/educelabid/{uuid}/datasets`, `/resolve`
- write (POST): `/pipelines`, `/pipelines/{id}/processes`

Cleanup (`el-hercdb-pipeline-cleanup`) runs on the VM against Neo4j directly — it
does not go through the REST API.
