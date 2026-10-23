"""#40 data fix: take EduceLabIDs off a PHerc that one of its own objects carries.

72, 1362 and 1363 each have their UUID on the papyrus and on its `Cass.` node.
The UUID names the cassetto piece (a tray), so the papyrus-level ASSIGNED_TO
goes. Only an edge whose UUID is also on a Cornice/Pezzo under that same PHerc
is removed, so a UUID that is on a PHerc alone is never touched. The loader
does the same on reload (`unassign_pherc_if_child_assigned`).

Modes (DEFAULT is read-only -- nothing is written without --apply):
  (no flag)  List the edges that would be removed.
  --apply    Remove them. Idempotent.

Run: uv run python preprocessing/fix_pherc_level_uuids.py            # list only
     uv run python preprocessing/fix_pherc_level_uuids.py --apply
"""

import argparse

from educelab import hercdb
from educelab.hercdb import config

_MATCH = """
    MATCH (e:EduceLabID)-[r:ASSIGNED_TO]->(ph:PHerc)
    WHERE EXISTS { (ph)-[:HAS*1..2]->()<-[:ASSIGNED_TO]-(e) }
"""


def analyze(db):
    records, _, _ = db._run_query(_MATCH + """
        RETURN e.uuid AS uuid, ph.displayName AS pherc,
               [(ph)-[:HAS*1..2]->(c)<-[:ASSIGNED_TO]-(e) | c.displayName] AS objects
        ORDER BY pherc
    """)
    if records is None:
        raise SystemExit("Query failed.")
    for r in records:
        print(f"  {r['uuid']}  PHerc {r['pherc']:<6} also on {r['objects']}")
    print(f"\n{len(records)} papyrus-level assignment(s) to remove.")
    return len(records)


def apply(db):
    records, _, _ = db._run_query(_MATCH + "DELETE r RETURN count(r) AS n")
    if records is None:
        raise SystemExit("Delete failed; nothing reported as written.")
    print(f"Removed {records[0]['n']} ASSIGNED_TO edge(s).")


def main():
    parser = argparse.ArgumentParser(description="Remove papyrus-level UUIDs a child also carries (#40).")
    parser.add_argument("--apply", action="store_true", help="Remove the edges.")
    args = parser.parse_args()

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    print("=== ANALYZE ===")
    analyze(db)

    if args.apply:
        print("\n=== APPLY ===")
        apply(db)
    else:
        print("\n(analyze only -- re-run with --apply to write)")


if __name__ == "__main__":
    main()
