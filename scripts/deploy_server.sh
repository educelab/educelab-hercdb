#!/usr/bin/env bash
#
# deploy_server.sh — install one released educelab-hercdb version into the
# REST server's venv, restart the service, and confirm it serves that version.
#
#   deploy_server.sh 0.3.10      # deploy (or roll back to) exactly 0.3.10
#
# The server runs from a venv holding a PyPI release, never from a git checkout,
# so the version it reports is a tag anyone can look up. Rollback is the same
# command with the previous version. See docs/SERVER_SETUP.md ("Deploying a
# release") and add an entry to docs/deploy_log.md for each deploy.
#
# Run as the service user (who owns the venv and ~/.educedb / ~/.tokens), not
# as root; it uses sudo only for systemctl. Install it once with
#   sudo install -m 755 scripts/deploy_server.sh /usr/local/sbin/hercdb_deploy
set -euo pipefail

# ---- config (override via the environment) ----------------------------------
VENV="${VENV:-$HOME/hercdb-server}"     # the venv hercdb.service runs from
SERVICE="${SERVICE:-hercdb}"            # systemd unit name
URL="${URL:-http://localhost:8000}"     # where the server answers on this host
WAIT_SECONDS="${WAIT_SECONDS:-60}"      # how long to wait for it to come back
# -----------------------------------------------------------------------------

die() { echo "deploy_server: $*" >&2; exit 1; }

version="${1:-}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "usage: $0 X.Y.Z (an exact released version)"
[[ "$(id -u)" -ne 0 ]] || die "run as the service user, not root (it calls sudo itself)"
[[ -x "$VENV/bin/python" ]] || die "no venv at $VENV; create it with: uv venv $VENV"
command -v uv >/dev/null || die "uv is not on PATH"

installed() {
    "$VENV/bin/python" -c "import importlib.metadata as m; print(m.version('educelab-hercdb'))" 2>/dev/null || echo none
}

served() {
    curl -fsS --max-time 5 "$URL/openapi.json" 2>/dev/null \
        | "$VENV/bin/python" -c "import json, sys; print(json.load(sys.stdin)['info']['version'])" 2>/dev/null
}

previous="$(installed)"
echo "installed: $previous -> deploying: $version"

# --refresh-package: a version published minutes ago may not be in uv's cached index yet.
uv pip install --python "$VENV/bin/python" --refresh-package educelab-hercdb \
    "educelab-hercdb[server]==$version"
[[ "$(installed)" == "$version" ]] || die "venv reports $(installed) after install, expected $version"

sudo systemctl restart "$SERVICE"

for ((i = 0; i < WAIT_SECONDS; i += 2)); do
    now="$(served || true)"
    if [[ "$now" == "$version" ]]; then
        echo "OK: $SERVICE serves $version at $URL"
        [[ "$previous" == "none" || "$previous" == "$version" ]] || echo "rollback: $0 $previous"
        exit 0
    fi
    sleep 2
done

echo "deploy_server: $SERVICE does not report $version after ${WAIT_SECONDS}s (got: ${now:-no answer})" >&2
echo "  check: sudo systemctl status $SERVICE; journalctl -u $SERVICE -n 50" >&2
[[ "$previous" == "none" ]] || echo "  rollback: $0 $previous" >&2
exit 1
