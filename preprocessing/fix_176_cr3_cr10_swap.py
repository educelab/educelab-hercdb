"""#49 data fix: swap the EduceLabIDs of PHerc 176 Cornice 3 and Cornice 10.

The papyrologists report the two trays were labelled the wrong way round at
imaging: the tray scanned 2022-12-22 as "Cr 3" (d52ae541) is Cornice 10, and
the one scanned 2022-12-23 as "Cr 10" (9a333479) is Cornice 3. An EduceLabID
names the physical tray, so the UUIDs and their datasets stay as they are and
only the two ASSIGNED_TO edges move.

The source sheets are NOT corrected (they are snapshots and not expected to be
reloaded). A reload from them would put the old edges back; see
docs/data_review_notes.md section 11 before reloading.

Both edges change in one transaction, and only from the exact state below:
  before:  d52ae541 -> 176/3    9a333479 -> 176/10
  after:   d52ae541 -> 176/10   9a333479 -> 176/3
Already in the "after" state -> nothing to do. Any other state -> refuse.

Modes (DEFAULT is read-only -- nothing is written without --apply):
  (no flag)  Show the current assignment and what would change.
  --apply    Swap the edges. Idempotent.

Run: uv run python preprocessing/fix_176_cr3_cr10_swap.py            # check only
     uv run python preprocessing/fix_176_cr3_cr10_swap.py --apply
"""

import argparse

from educelab import hercdb
from educelab.hercdb import config

PHERC = "176"
CR03_TRAY = "d52ae541-5f2c-5381-a2d6-bc845698f23e"  # labelled Cr 3, is Cornice 10
CR10_TRAY = "9a333479-f5e0-589c-a6c5-507332bc2b35"  # labelled Cr 10, is Cornice 3

BEFORE = {CR03_TRAY: ["3"], CR10_TRAY: ["10"]}
AFTER = {CR03_TRAY: ["10"], CR10_TRAY: ["3"]}

_STATE = """
    UNWIND $uuids AS u
    MATCH (e:EduceLabID {uuid: u})
    RETURN e.uuid AS uuid,
           [(e)-[:ASSIGNED_TO]->(n) |
              coalesce([(p:PHerc)-[:HAS]->(n) | p.displayName][0], '-') + '/' + n.displayName] AS targets
"""

_SWAP = """
    MATCH (ph:PHerc {displayName: $pherc})
    MATCH (ph)-[:HAS]->(c3:Cornice {displayName: '3'})
    MATCH (ph)-[:HAS]->(c10:Cornice {displayName: '10'})
    MATCH (a:EduceLabID {uuid: $cr03_tray})-[ra:ASSIGNED_TO]->(c3)
    MATCH (b:EduceLabID {uuid: $cr10_tray})-[rb:ASSIGNED_TO]->(c10)
    DELETE ra, rb
    MERGE (a)-[:ASSIGNED_TO]->(c10)
    MERGE (b)-[:ASSIGNED_TO]->(c3)
    RETURN count(*) AS swapped
"""


def current_state(db):
    records, _, _ = db._run_query(_STATE, uuids=[CR03_TRAY, CR10_TRAY])
    state = {r["uuid"]: sorted(r["targets"]) for r in records}
    for u in (CR03_TRAY, CR10_TRAY):
        print(f"  {u}  -> {state.get(u, 'MISSING')}")
    # Keep only the cornice part of 'pherc/cornice', checking the PHerc on the way.
    simple = {}
    for u, targets in state.items():
        if any(not t.startswith(f"{PHERC}/") for t in targets):
            simple[u] = targets  # something other than 176's cornici: won't match
        else:
            simple[u] = [t.split("/", 1)[1] for t in targets]
    return simple


def main():
    parser = argparse.ArgumentParser(description="Swap PHerc 176 Cornice 3 / Cornice 10 UUIDs (#49).")
    parser.add_argument("--apply", action="store_true", help="Swap the edges.")
    args = parser.parse_args()

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")
    print(f"Target: {db.uri}")

    print("=== CURRENT ===")
    state = current_state(db)

    if state == AFTER:
        print("\nAlready swapped. Nothing to do.")
        return
    if state != BEFORE:
        raise SystemExit(f"\nUnexpected state; refusing to write. Expected {BEFORE}.")

    print(f"\nWill move {CR03_TRAY[:8]} to {PHERC}/10 and {CR10_TRAY[:8]} to {PHERC}/3.")
    if not args.apply:
        print("(check only -- re-run with --apply to write)")
        return

    print("\n=== APPLY ===")
    records, _, _ = db._run_query(_SWAP, pherc=PHERC, cr03_tray=CR03_TRAY, cr10_tray=CR10_TRAY)
    if not records or records[0]["swapped"] != 1:
        raise SystemExit("Swap matched nothing; no change written.")
    print("Swapped. Now:")
    if current_state(db) != AFTER:
        raise SystemExit("Read-back does not match the expected state -- check by hand.")
    print("Read-back OK.")


if __name__ == "__main__":
    main()
