#!/usr/bin/env bash
#
# neo4j_dev_refresh.sh — reload the DEV Neo4j from last night's prod dump.
#
# Runs on the backup/dev VM, where prod's neo4j_backup.sh ships its nightly
# dumps (~03:30). Loads the newest neo4j-*.dump and its matching system-*.dump
# over the dev "neo4j" and "system" databases, so anything tests wrote to dev
# is wiped and dev's users/passwords become prod's.
#
# Run as root from cron, after the dump has arrived:
#   0 4 * * *  /usr/local/sbin/neo4j_dev_refresh.sh
#
# An EXIT trap always restarts Neo4j, so a failed load never leaves it down.
set -euo pipefail

DUMP_DIR="${DUMP_DIR:-/home/hercdb-backup/neo4j-dumps}"
STAGING_DIR="${STAGING_DIR:-/var/tmp/neo4j-restore}"  # disk-backed, unlike a tmpfs /tmp
MAX_AGE_HOURS="${MAX_AGE_HOURS:-24}"                  # refuse a dump older than this
MIN_DUMP_BYTES="${MIN_DUMP_BYTES:-1048576}"
NEO4J_SERVICE="${NEO4J_SERVICE:-neo4j}"
NEO4J_ADMIN="${NEO4J_ADMIN:-/usr/bin/neo4j-admin}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
BOLT_PORT="${BOLT_PORT:-7687}"
LOG="${LOG:-/var/log/neo4j_dev_refresh.log}"

exec >>"$LOG" 2>&1
echo "=== $(date -Is) dev refresh start ==="

# Newest dump by name: the YYYYmmdd-HHMMSS stamp makes glob order date order.
# rsync writes to a hidden temp file and renames it when done, so a file with
# this name is complete.
shopt -s nullglob
dumps=("$DUMP_DIR"/neo4j-*.dump)
[ ${#dumps[@]} -gt 0 ] || { echo "ERROR: no neo4j-*.dump in $DUMP_DIR"; exit 1; }
latest="${dumps[-1]}"
echo "newest dump: $latest ($(du -h "$latest" | cut -f1))"

# An old newest dump means last night's backup didn't arrive; keep dev as it is.
if [ -z "$(find "$latest" -mmin -$((MAX_AGE_HOURS * 60)))" ]; then
    echo "ERROR: $latest is older than ${MAX_AGE_HOURS}h; did last night's backup run? Not loading."
    exit 1
fi
[ "$(stat -c%s "$latest")" -gt "$MIN_DUMP_BYTES" ] || { echo "ERROR: $latest is too small"; exit 1; }

# The system dump from the same backup run carries the same timestamp.
stamp="${latest##*/neo4j-}"                  # e.g. 20261102-033001.dump
system_dump="$DUMP_DIR/system-$stamp"
[ -s "$system_dump" ] || { echo "ERROR: no matching $system_dump"; exit 1; }

# load reads <db>.dump from --from-path and runs as the neo4j user, which
# can't read DUMP_DIR, so stage copies it owns.
mkdir -p "$STAGING_DIR"
cp "$latest" "$STAGING_DIR/neo4j.dump"
cp "$system_dump" "$STAGING_DIR/system.dump"
chown -R "$NEO4J_USER" "$STAGING_DIR"

trap 'systemctl start "$NEO4J_SERVICE" || echo "WARN: failed to restart $NEO4J_SERVICE"' EXIT
systemctl stop "$NEO4J_SERVICE"
for db in neo4j system; do
    sudo -u "$NEO4J_USER" "$NEO4J_ADMIN" database load "$db" \
         --from-path="$STAGING_DIR" --overwrite-destination=true
done
systemctl start "$NEO4J_SERVICE"
trap - EXIT
rm -f "$STAGING_DIR/neo4j.dump" "$STAGING_DIR/system.dump"

# Wait up to 2 minutes for Neo4j to accept Bolt connections.
for _ in $(seq 24); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$BOLT_PORT") 2>/dev/null; then
        echo "=== $(date -Is) dev refresh OK: loaded neo4j + system from $stamp ==="
        exit 0
    fi
    sleep 5
done
echo "ERROR: Neo4j did not open port $BOLT_PORT within 2 minutes of the load"
exit 1
