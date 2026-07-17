#!/usr/bin/env bash
#
# neo4j_backup.sh — nightly OFFLINE backup of the hercdb Neo4j databases.
#
# Neo4j Community Edition has no online backup, so this briefly stops Neo4j,
# dumps the offline databases, restarts it, then ships the timestamped dumps to
# a cold-spare VM over SSH and prunes old dumps on both ends.
#
# Dumps BOTH the data database ("neo4j") AND the "system" database. system holds
# DBMS metadata — user accounts/passwords and the database catalog — so it is
# needed for a faithful from-scratch restore (per the Neo4j Operations Manual:
# "back up each of your databases, including the system database"). Not
# Kubernetes-specific; system exists in every Neo4j deployment.
#
# Runs on the PRIMARY VM as root (or a user with sudo for systemctl + the neo4j
# user). Scheduled via cron. See docs/BACKUP.md.
#
# Safety: an EXIT trap ALWAYS restarts Neo4j, so a failed dump never leaves the
# database down. The trap is cleared only after a confirmed restart.
set -euo pipefail

# ---- config (edit for your environment, or override via the environment) ----
DATABASES="${DATABASES:-neo4j system}"             # databases to dump (data DB + system)
STAGING_DIR="${STAGING_DIR:-/var/backups/neo4j}"   # local staging + cache (root-owned)
LOCAL_KEEP_DAYS="${LOCAL_KEEP_DAYS:-3}"            # small local cache
REMOTE_USER="${REMOTE_USER:-hercdb-backup}"
REMOTE_HOST="${REMOTE_HOST:-backup-vm.example}"    # hostname or IP
REMOTE_DIR="${REMOTE_DIR:-/home/hercdb-backup/neo4j-dumps}"
REMOTE_KEEP_DAYS="${REMOTE_KEEP_DAYS:-14}"
SSH_KEY="${SSH_KEY:-/root/.ssh/hercdb_backup}"
LOG="${LOG:-/var/log/neo4j_backup.log}"
NEO4J_SERVICE="${NEO4J_SERVICE:-neo4j}"            # systemd unit name for Neo4j
# neo4j-admin path: system pkg -> /usr/bin/neo4j-admin ; tarball -> $NEO4J_HOME/bin
NEO4J_ADMIN="${NEO4J_ADMIN:-/usr/bin/neo4j-admin}"
NEO4J_USER="${NEO4J_USER:-neo4j}"                  # OS user that owns the store
MIN_FREE_MB="${MIN_FREE_MB:-500}"                  # abort dump if staging has less free
MIN_DUMP_BYTES="${MIN_DUMP_BYTES:-1024}"           # reject an implausibly small dump
# Optional dead-man's-switch: if set, pinged with curl on success (see docs/BACKUP.md).
HEARTBEAT_URL="${HEARTBEAT_URL:-}"
# -----------------------------------------------------------------------------

TS="$(date +%Y%m%d-%H%M%S)"
exec >>"$LOG" 2>&1
echo "=== $(date -Is) backup start (databases: $DATABASES) ==="

mkdir -p "$STAGING_DIR"
# The dump runs as $NEO4J_USER (sudo -u), so that user must be able to write into
# the staging dir. The script itself runs as root, so the later mv/rsync/prune work
# regardless of ownership.
chown "$NEO4J_USER" "$STAGING_DIR"

# Pre-flight: enough free space in the staging dir to hold the dumps?
free_mb="$(df -Pm "$STAGING_DIR" | awk 'NR==2 {print $4}')"
if [ "${free_mb:-0}" -lt "$MIN_FREE_MB" ]; then
    echo "ERROR: only ${free_mb}MB free in $STAGING_DIR (need >= ${MIN_FREE_MB}MB); aborting."
    exit 1
fi

restart_neo4j() { systemctl start "$NEO4J_SERVICE" || echo "WARN: failed to restart $NEO4J_SERVICE"; }
trap restart_neo4j EXIT           # guarantees the DB comes back up on any exit path

systemctl stop "$NEO4J_SERVICE"
# Dump each OFFLINE database (run as the neo4j user so store perms are respected).
# neo4j-admin writes <db>.dump into --to-path, overwriting on each run. Both dumps
# happen inside the single stop window, so system adds only negligible downtime.
for db in $DATABASES; do
    sudo -u "$NEO4J_USER" "$NEO4J_ADMIN" database dump "$db" \
         --to-path="$STAGING_DIR" --overwrite-destination=true
done
systemctl start "$NEO4J_SERVICE"
trap - EXIT                        # dumps done and DB is back; clear the safety trap

# Timestamp each fresh dump so retention/rotation has distinct filenames.
dumps=()
for db in $DATABASES; do
    dump="$STAGING_DIR/${db}-${TS}.dump"
    mv "$STAGING_DIR/${db}.dump" "$dump"
    echo "created $dump ($(du -h "$dump" | cut -f1))"
    # Sanity: refuse to ship an implausibly small dump.
    test "$(stat -c%s "$dump")" -gt "$MIN_DUMP_BYTES" || { echo "ERROR: $db dump too small"; exit 1; }
    dumps+=("$dump")
done

# Ship all dumps to the backup VM.
rsync -av -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new" \
      "${dumps[@]}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

# Prune: local cache + remote retention, per database.
for db in $DATABASES; do
    find "$STAGING_DIR" -name "${db}-*.dump" -mtime +"${LOCAL_KEEP_DAYS}" -delete
done
ssh -i "$SSH_KEY" "${REMOTE_USER}@${REMOTE_HOST}" \
    "for db in $DATABASES; do find '${REMOTE_DIR}' -name \"\${db}-*.dump\" -mtime +${REMOTE_KEEP_DAYS} -delete; done"

# Success heartbeat (dead-man's-switch), so a run that silently stops firing is noticed.
if [ -n "$HEARTBEAT_URL" ]; then
    curl -fsS -m 10 --retry 3 "$HEARTBEAT_URL" >/dev/null \
        && echo "heartbeat pinged" || echo "WARN: heartbeat ping failed"
fi

echo "=== $(date -Is) backup OK ==="
