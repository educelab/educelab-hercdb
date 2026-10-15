"""0.3.9 migration: give processed datasets their own `uuid`.

Before 0.3.9 the pipelines minted a UUID for each output and wrote it to the
output's `metadata.json`, but never sent it, so PGSProcessed, SpectralProcessed,
Registered and WebProcessed nodes have none. This reads it back from the data
store, `<data_root>/<path>/metadata.json` (top-level `uuid`), for every
processed dataset without one. Raw scans already carry theirs.

Accepted only from pipeline metadata (it has `schema_version` and
`dataset_type`; pre-2.0 pgs-recon wrote a different file under the same name),
and only when no other dataset already has that UUID. A rerun to the same path
overwrote its metadata, so the UUID read is the latest run's.

Modes (DEFAULT is read-only analysis -- nothing is written without --apply):
  (no flag)       Report what each dataset would get, with examples. No writes.
  --apply         Write the UUIDs read from metadata.json, and create a uuid
                  index on each dataset label.
  --mint-missing  With --apply, also mint a new UUID for every dataset whose
                  metadata.json is missing or unusable.

Run: uv run python preprocessing/migrate_dataset_uuids.py --data-root /mnt/herc
     uv run python preprocessing/migrate_dataset_uuids.py --data-root /mnt/herc --apply
     uv run python preprocessing/migrate_dataset_uuids.py --data-root /mnt/herc --apply --mint-missing
"""

import argparse
import json
import uuid as uuid_lib
from collections import Counter, defaultdict
from pathlib import Path

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.db.connection import _PROCESSED_DATASET_LABELS, _RELEASABLE_DATASET_LABELS

_PROCESSED_TEST = " OR ".join(f"d:{label}" for label in _PROCESSED_DATASET_LABELS)
_RELEASABLE_TEST = " OR ".join(f"d:{label}" for label in _RELEASABLE_DATASET_LABELS)

FROM_METADATA = "from metadata.json"
NO_FILE = "no metadata.json"
UNREADABLE = "metadata.json unreadable"
NOT_PIPELINE = "not pipeline metadata"
NO_UUID = "no valid uuid in metadata.json"
DUPLICATE = "uuid already used"


def fetch(db):
    """Processed datasets with no uuid, and every dataset uuid already in use."""
    missing, _, _ = db._run_query(f"""
        MATCH (d) WHERE ({_PROCESSED_TEST}) AND d.uuid IS NULL
        RETURN elementId(d) AS id, [l IN labels(d) WHERE l IN $labels][0] AS type, d.path AS path
    """, labels=_PROCESSED_DATASET_LABELS)
    taken, _, _ = db._run_query(f"""
        MATCH (d) WHERE ({_RELEASABLE_TEST}) AND d.uuid IS NOT NULL
        RETURN d.uuid AS uuid
    """)
    if missing is None or taken is None:
        raise SystemExit("Query failed.")
    return [dict(r) for r in missing], {r["uuid"] for r in taken}


def read_uuid(data_root: Path, path: str | None) -> tuple[str, str | None]:
    """(outcome, uuid) for one dataset's metadata.json."""
    if not path:
        return NO_FILE, None
    file = data_root / path.strip("/") / "metadata.json"
    try:
        meta = json.loads(file.read_text())
    except FileNotFoundError:
        return NO_FILE, None
    except (OSError, ValueError):
        return UNREADABLE, None
    if not isinstance(meta, dict) or "schema_version" not in meta or "dataset_type" not in meta:
        return NOT_PIPELINE, None
    try:
        return FROM_METADATA, str(uuid_lib.UUID(str(meta.get("uuid"))))
    except ValueError:
        return NO_UUID, None


def plan(rows, taken, data_root: Path):
    """Each dataset's outcome, refusing a uuid another dataset (or an earlier row) has."""
    seen = set(taken)
    for row in rows:
        outcome, value = read_uuid(data_root, row["path"])
        if value is not None and value in seen:
            outcome, value = DUPLICATE, None
        if value is not None:
            seen.add(value)
        row["outcome"], row["uuid"] = outcome, value
    return rows


def report(rows):
    by_outcome = defaultdict(list)
    for row in rows:
        by_outcome[row["outcome"]].append(row)
    print(f"{len(rows)} processed dataset(s) without a uuid.\n")
    for outcome, group in sorted(by_outcome.items(), key=lambda kv: -len(kv[1])):
        types = Counter(r["type"] for r in group)
        print(f"  {outcome:<32} {len(group):>6}   " + ", ".join(f"{t} {n}" for t, n in sorted(types.items())))
        for r in group[:3]:
            print(f"      e.g. {r['path']}")


def apply(db, rows, mint_missing: bool):
    writes = []
    for row in rows:
        value = row["uuid"]
        if value is None and mint_missing:
            value = str(uuid_lib.uuid4())
        if value is not None:
            writes.append({"id": row["id"], "uuid": value})
    records, _, _ = db._run_query("""
        UNWIND $writes AS w
        MATCH (d) WHERE elementId(d) = w.id AND d.uuid IS NULL
        SET d.uuid = w.uuid
        RETURN count(d) AS n
    """, writes=writes)
    if records is None:
        raise SystemExit("Backfill failed; nothing reported as written.")
    print(f"Set uuid on {records[0]['n']} dataset(s).")

    for label in _RELEASABLE_DATASET_LABELS:
        db._run_query(f"CREATE INDEX {label.lower()}_uuid IF NOT EXISTS FOR (d:{label}) ON (d.uuid)")
    print("Ensured a uuid index on each dataset label.")


def main():
    parser = argparse.ArgumentParser(description="Backfill processed dataset UUIDs (analyze by default).")
    parser.add_argument("--data-root", required=True, type=Path,
                        help="Directory dataset paths are relative to.")
    parser.add_argument("--apply", action="store_true", help="Write the UUIDs.")
    parser.add_argument("--mint-missing", action="store_true",
                        help="With --apply, mint a UUID where metadata.json gives none.")
    args = parser.parse_args()
    if not args.data_root.is_dir():
        raise SystemExit(f"{args.data_root} is not a directory.")

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    rows, taken = fetch(db)
    rows = plan(rows, taken, args.data_root)
    print("=== ANALYZE ===")
    report(rows)

    if args.apply:
        print("\n=== APPLY ===")
        apply(db, rows, args.mint_missing)
    else:
        print("\n(analyze only -- re-run with --apply to write, adding --mint-missing to fill the rest)")


if __name__ == "__main__":
    main()
