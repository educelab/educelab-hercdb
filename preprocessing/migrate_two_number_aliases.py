"""#45 migration: add each number of a two-number papyrus to its aliases.

"1007/1673" is one papyrus catalogued under two numbers, and neither number has
a node of its own, so a search for "1673" should find it. The loader now adds
the parts (PhercGraphDatabaseLoader._pherc_aliases); this brings an existing
graph in line, reusing the same helper. displayName is not changed.

Modes (DEFAULT is read-only -- nothing is written without --apply):
  (no flag)  List the aliases that would be added.
  --apply    Add them. Idempotent.

Run: uv run python preprocessing/migrate_two_number_aliases.py            # list only
     uv run python preprocessing/migrate_two_number_aliases.py --apply
"""

import argparse

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader as L


def plan(db) -> list[dict]:
    records, _, _ = db._run_query("""
        MATCH (p:PHerc) WHERE p.displayName CONTAINS '/'
        RETURN elementId(p) AS id, p.displayName AS name, p.aliases AS aliases
        ORDER BY name
    """)
    if records is None:
        raise SystemExit("Query failed.")
    changes = []
    for r in records:
        if not L._TWO_NUMBERS.match(r['name']):
            continue
        have = r['aliases'] or []
        add = [a for a in L._pherc_aliases(r['name']) if a not in have]
        if add:
            changes.append({'id': r['id'], 'name': r['name'], 'add': add, 'aliases': have + add})
    return changes


def apply(db, changes):
    for c in changes:
        records, _, _ = db._run_query("""
            MATCH (p:PHerc) WHERE elementId(p) = $id
            SET p.aliases = $aliases
            RETURN count(p) AS n
        """, id=c['id'], aliases=c['aliases'])
        if not records or records[0]['n'] != 1:
            raise SystemExit(f"Update failed on {c['name']!r}; stopping.")
    print(f"Added aliases to {len(changes)} papyri.")


def main():
    parser = argparse.ArgumentParser(description="Add two-number papyri's parts to their aliases (#45).")
    parser.add_argument("--apply", action="store_true", help="Add them.")
    args = parser.parse_args()

    config.request_required()
    print(f"Target: {config.uri}")
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    print("=== ANALYZE ===")
    changes = plan(db)
    for c in changes:
        print(f"  {c['name']:<10} add {c['add']}")
    print(f"\n{len(changes)} papyri to update.")

    if args.apply:
        print("\n=== APPLY ===")
        apply(db, changes)
    else:
        print("\n(analyze only -- re-run with --apply to write)")


if __name__ == "__main__":
    main()
