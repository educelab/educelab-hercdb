"""0.3.9 migration: give every releasable dataset an explicit `released` flag.

Datasets written before 0.3.9 have none. New ones get `config.release_default()`
when created, so this backfills the existing ones to match. Flatbed negatives are
not releasable and are left alone.

Modes (DEFAULT is read-only analysis -- nothing is written without --apply):
  (no flag)  Count datasets per type with and without a flag. No writes.
  --apply    Set released = <value> where it is unset. Idempotent: a flag
             already present (a reviewer's decision) is never overwritten.

Run: uv run python preprocessing/migrate_release_flag.py            # analyze only
     uv run python preprocessing/migrate_release_flag.py --apply    # backfill true
     uv run python preprocessing/migrate_release_flag.py --apply --value false
"""

import argparse

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.db.connection import _RELEASABLE_DATASET_LABELS

_LABEL_TEST = " OR ".join(f"d:{label}" for label in _RELEASABLE_DATASET_LABELS)


def analyze(db):
    records, _, _ = db._run_query(f"""
        MATCH (d) WHERE {_LABEL_TEST}
        WITH [l IN labels(d) WHERE l IN $labels][0] AS type, d.released AS released
        RETURN type, released, count(*) AS n
        ORDER BY type, released
    """, labels=_RELEASABLE_DATASET_LABELS)
    if records is None:
        raise SystemExit("Query failed.")
    unset = 0
    for r in records:
        print(f"  {r['type']:<18} released={str(r['released']):<5} {r['n']:>6}")
        if r["released"] is None:
            unset += r["n"]
    print(f"\n{unset} dataset(s) without a flag.")
    return unset


def apply(db, value: bool):
    records, _, _ = db._run_query(f"""
        MATCH (d) WHERE ({_LABEL_TEST}) AND d.released IS NULL
        SET d.released = $value
        RETURN count(d) AS n
    """, value=value)
    if records is None:
        raise SystemExit("Backfill failed; nothing reported as written.")
    print(f"Set released={value} on {records[0]['n']} dataset(s).")


def main():
    parser = argparse.ArgumentParser(description="Backfill dataset release flags (analyze by default).")
    parser.add_argument("--apply", action="store_true", help="Write the flag where it is unset.")
    parser.add_argument("--value", choices=("true", "false"), default="true",
                        help="Flag to backfill (default true, for the first pass over the data).")
    args = parser.parse_args()

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    print("=== ANALYZE ===")
    analyze(db)

    if args.apply:
        print("\n=== APPLY ===")
        apply(db, args.value == "true")
    else:
        print("\n(analyze only -- re-run with --apply to write)")


if __name__ == "__main__":
    main()
