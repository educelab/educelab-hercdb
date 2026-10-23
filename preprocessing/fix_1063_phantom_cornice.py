"""#59 data fix: remove the phantom Cornice 1 (Fackelmann) under PHerc 1063.

The metadata loader hard-coded PHerc "1063" instead of "1073" for tray
d5b9ebc4 (228, 444, 1073 in both source sheets), which created this node and
assigned the tray's UUID to it. The node is deleted only if nothing but that
HAS and that ASSIGNED_TO touches it, and only once 1073 carries the UUID.

Modes (DEFAULT is read-only -- nothing is written without --apply):
  (no flag)  Show the node and everything attached to it.
  --apply    Delete it, if it is still only the phantom. Idempotent.

Run: uv run python preprocessing/fix_1063_phantom_cornice.py            # show only
     uv run python preprocessing/fix_1063_phantom_cornice.py --apply
"""

import argparse

from educelab import hercdb
from educelab.hercdb import config

UUID = "d5b9ebc4-31a9-5368-90ac-eeb2893998db"

_MATCH = """
    MATCH (:PHerc {displayName: '1063'})-[:HAS]->(c:Cornice {displayName: '1 (Fackelmann)'})
          <-[:ASSIGNED_TO]-(:EduceLabID {uuid: $uuid})
    WHERE COUNT { (c)--() } = 2
      AND EXISTS { (:PHerc {displayName: '1073'})-[:HAS]->(:Cornice)<-[:ASSIGNED_TO]-(:EduceLabID {uuid: $uuid}) }
"""


def analyze(db):
    records, _, _ = db._run_query("""
        MATCH (:PHerc {displayName: '1063'})-[:HAS]->(c:Cornice)
        RETURN c.displayName AS cornice,
               [(c)-[r]-(m) | type(r) + ' ' + coalesce(m.displayName, m.uuid, '?')] AS attached
    """)
    if records is None:
        raise SystemExit("Query failed.")
    for r in records:
        print(f"  PHerc 1063 / {r['cornice']}: {r['attached']}")
    phantom, _, _ = db._run_query(_MATCH + "RETURN count(c) AS n", uuid=UUID)
    n = phantom[0]['n'] if phantom else 0
    print(f"\n{n} phantom cornice(s) to delete.")
    return n


def apply(db):
    records, _, _ = db._run_query(_MATCH + "DETACH DELETE c RETURN count(*) AS n", uuid=UUID)
    if records is None:
        raise SystemExit("Delete failed; nothing reported as written.")
    print(f"Deleted {records[0]['n']} node(s).")


def main():
    parser = argparse.ArgumentParser(description="Remove the phantom 1063 cornice (#59).")
    parser.add_argument("--apply", action="store_true", help="Delete it.")
    args = parser.parse_args()

    config.request_required()
    print(f"Target: {config.uri}")
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
