# Neo4j Backup & Restore Runbook

Nightly offline backup of the hercdb Neo4j database, pushed to a cold-spare VM.

## Why offline

hercdb runs **Neo4j Community Edition**, which has **no online backup**
(`neo4j-admin database backup` is Enterprise-only). Community can only *dump an
offline database* — `neo4j-admin database dump` refuses to run against a live
DBMS. So each backup cycle briefly **stops Neo4j, dumps, and restarts it**. For a
small store this is seconds to ~1 minute; it is scheduled in the middle of the
night.

Both the **`neo4j`** data database **and** the **`system`** database are dumped
(the Operations Manual: "back up each of your databases, including the system
database"). `system` holds DBMS metadata — user accounts/passwords and the
database catalog — so it is needed for a faithful from-scratch restore. Dumping
only `neo4j` still recovers all graph data, but a rebuilt instance would come up
with no users until you re-provision them. Both dumps happen inside the one stop
window, so `system` adds only negligible downtime.

During that window the REST API stays up but returns **HTTP 503** (not a
misleading 404) for any query that needs the DB, and `HercClient` retries
automatically — so writes from HPC pipeline callbacks ride over the outage
instead of being lost. (That write-path resilience is a prerequisite; see the
package CHANGELOG / branch `fix-neo4j-unavailable-503`.)

## Architecture

```
PRIMARY VM (neo4j + REST)                    BACKUP VM (cold spare)
┌─────────────────────────────┐             ┌──────────────────────────┐
│ cron (root) → neo4j_backup.sh│             │ hercdb-backup user        │
│   1. stop neo4j              │   rsync     │   ~/neo4j-dumps/          │
│   2. dump neo4j + system     │  ─────────▶ │     neo4j-20260706-…dump  │
│   3. start neo4j             │  over SSH   │     system-20260706-…dump │
│   4. timestamp + ship + prune│             │     …(14 days)            │
└─────────────────────────────┘             │  (no running Neo4j needed)│
                                             └──────────────────────────┘
```

- Backup VM is **cold storage of `.dump` files only** — no running Neo4j.
- Transfer is **pushed from the primary** over SSH (rsync).
- Retention: **14 days** on the backup VM, a small **3-day** cache on the primary.

The script (`scripts/neo4j_backup.sh`) only stops the **`neo4j`** service; it does
**not** touch the `hercdb` REST unit. An `EXIT` trap **always restarts Neo4j**, so a
failed dump never leaves the database down.

---

## One-time setup

### On the BACKUP VM

```bash
# Dedicated, unprivileged user that owns only the dump directory.
sudo useradd -m -s /bin/bash hercdb-backup
sudo -u hercdb-backup mkdir -p /home/hercdb-backup/neo4j-dumps
sudo -u hercdb-backup chmod 700 /home/hercdb-backup/neo4j-dumps
```

### On the PRIMARY VM

```bash
# Dedicated SSH key for the transfer (no passphrase, root-owned).
sudo ssh-keygen -t ed25519 -f /root/.ssh/hercdb_backup -N "" -C "hercdb-backup"
# Staging dir must be writable by the neo4j user (the dump runs as that user).
# The script also enforces this each run, but set it up front too:
sudo mkdir -p /var/backups/neo4j
sudo chown neo4j /var/backups/neo4j

# Install the backup script.
sudo cp scripts/neo4j_backup.sh /usr/local/sbin/neo4j_backup.sh
sudo chmod 755 /usr/local/sbin/neo4j_backup.sh
```

Install the **public** key into `hercdb-backup@backup-vm:~/.ssh/authorized_keys`,
locked down to the primary:

```
from="<primary-ip>",no-agent-forwarding,no-port-forwarding,no-pty ssh-ed25519 AAAA...
```

(A forced-command `rrsync` wrapper is an optional further hardening step.)

The script runs as root, so `sudo -u neo4j neo4j-admin …` and `systemctl
stop/start neo4j` need no sudoers edits. If you instead schedule it under a
non-root user, add sudoers rules for those commands.

---

## Configuration

Edit the config block at the top of `neo4j_backup.sh`, or override any value via
the environment (each uses `${VAR:-default}`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `DATABASES` | `neo4j system` | Databases to dump (data DB + system metadata) |
| `STAGING_DIR` | `/var/backups/neo4j` | Local staging + cache (root-owned) |
| `LOCAL_KEEP_DAYS` | `3` | Local cache retention |
| `REMOTE_USER` / `REMOTE_HOST` / `REMOTE_DIR` | `hercdb-backup` / `backup-vm.example` / `/home/hercdb-backup/neo4j-dumps` | Backup-VM target |
| `REMOTE_KEEP_DAYS` | `14` | Remote retention |
| `SSH_KEY` | `/root/.ssh/hercdb_backup` | SSH key for rsync/ssh |
| `NEO4J_SERVICE` | `neo4j` | systemd unit to stop/start |
| `NEO4J_ADMIN` | `/usr/bin/neo4j-admin` | `neo4j-admin` path (differs for tarball installs) |
| `NEO4J_USER` | `neo4j` | OS user that owns the store |
| `MIN_FREE_MB` | `500` | Abort if staging has less free space |
| `HEARTBEAT_URL` | *(unset)* | If set, pinged on success (see Monitoring) |

**Set at minimum `REMOTE_HOST`** (and `REMOTE_USER`/`REMOTE_DIR` if they differ).

> **Neo4j install note:** these defaults assume the **Debian/RPM package** install
> (service `neo4j`, `neo4j-admin` on `PATH`). For a **tarball** install, set
> `NEO4J_ADMIN=$NEO4J_HOME/bin/neo4j-admin` and adjust `NEO4J_SERVICE`. Confirm the
> deployed Neo4j version and re-check the exact `neo4j-admin` dump/load flags for it
> (syntax below is correct for Neo4j 5.x).

---

## Scheduling (cron)

Run nightly at 03:30 as root:

```bash
sudo crontab -e
```
```cron
30 3 * * *  /usr/local/sbin/neo4j_backup.sh
```

The script appends to its own log (`/var/log/neo4j_backup.log` by default), so no
cron redirection is needed. Tail it with `sudo tail -f /var/log/neo4j_backup.log`.

---

## Monitoring

A silently failing nightly backup is the classic way "we have backups" quietly
becomes false. Use a **dead-man's-switch**:

1. Create a check at a service such as [healthchecks.io](https://healthchecks.io)
   (self-hostable) with a period of ~1 day and a grace window.
2. Set `HEARTBEAT_URL` to its ping URL (in the script config, or the crontab line:
   `HEARTBEAT_URL=https://hc-ping.com/<uuid> /usr/local/sbin/neo4j_backup.sh`).

The script pings it **only on success** (last step), so a run that fails or never
fires triggers an alert from the monitoring service. This works regardless of the
scheduler and is the primary failure-notification mechanism.

---

## Restore / disaster recovery

On the backup VM (or a rebuilt primary) with the **same major Neo4j version**
installed and **stopped**. `load` reads `<db>.dump` from `--from-path`, so stage
each chosen timestamped dump under its plain `<db>.dump` name first:

```bash
# Stage the chosen dumps as neo4j.dump and system.dump (matching timestamps).
mkdir -p /tmp/restore
cp /home/hercdb-backup/neo4j-dumps/neo4j-YYYYmmdd-HHMMSS.dump  /tmp/restore/neo4j.dump
cp /home/hercdb-backup/neo4j-dumps/system-YYYYmmdd-HHMMSS.dump /tmp/restore/system.dump

sudo systemctl stop neo4j
# Data database (your graph):
sudo -u neo4j neo4j-admin database load neo4j \
     --from-path=/tmp/restore --overwrite-destination=true
# System database (users/passwords + catalog) — for a full DR that preserves auth:
sudo -u neo4j neo4j-admin database load system \
     --from-path=/tmp/restore --overwrite-destination=true
sudo systemctl start neo4j
```

Then verify (from `docs/SERVER_SETUP.md` step 5):

```bash
uv run python -c "from educelab.hercdb.db import connect; print(connect().verify_connection())"
```

**On restoring `system`:** it overwrites the target's user accounts and database
catalog with the dump's, and must be the **same Neo4j version**. Load it for a
faithful DR (users come back as they were). If you only need the **data** back and
would rather keep the target's existing auth, **skip the `system` load** and
instead set the password on the fresh instance (`neo4j-admin dbms
set-initial-password …`) — the `neo4j` data restore alone recovers the graph.

---

## Testing checklist (prove it before trusting it)

1. **Dry run** on the primary: `sudo /usr/local/sbin/neo4j_backup.sh`, then confirm
   `systemctl status neo4j` shows Neo4j came back up and the log ends with `backup OK`.
2. **Transfer + naming:** timestamped `neo4j-*.dump` **and** `system-*.dump` of
   plausible size appear in `hercdb-backup@backup-vm:~/neo4j-dumps/`.
3. **Failure-safety:** temporarily point `NEO4J_ADMIN` at a bad path, run the script,
   and confirm the EXIT trap **still restarted Neo4j** and the run exited non-zero
   (nothing shipped).
4. **Restore test — the real proof:** load the newest dump into a scratch/backup Neo4j
   per the DR procedure and run `verify_connection()`. *A dump you have never restored
   is not a backup.*
5. **Retention:** confirm dumps older than 14 days are pruned remotely and >3 days
   locally (fake with `touch -d` on test files).
6. **Measure the window:** time the actual `stop → dump → start`; confirm it is
   comfortably under the `HercClient` retry budget (~108s with defaults).
7. **Heartbeat:** confirm the monitoring check goes green after a successful run.

> `neo4j-admin database check` verifies store consistency but is heavy — run it as an
> occasional manual/weekly check, not nightly.
