"""#61 data fix: move a shared tray's uuid-sheet names off the nodes on it.

The loader used to copy a uuid-sheet row's names onto every node a shared tray's
UUID is assigned to, and onto every PHerc above them. So every papyrus on a shared
tray carries the row's list of papyri ("924-935", "1157-1191") as an alias and as
`name`, and 1191's "1 (Osloense)" carries 1157's "2 (oslo)".

On every EduceLabID assigned to more than one node, this:
  - removes from each PHerc an alias that every PHerc on the tray carries but that
    doesn't name this papyrus alone (graph_loader.names_papyrus);
  - removes from each Cornice/Pezzo an alias whose leading number differs from
    the node's own (graph_loader.same_number);
  - resets a `name` that was such a value to the node's displayName;
  - records the tray's sheet names on the EduceLabID as `sheet_pherc` /
    `sheet_cornice`, where they aren't set already.

Modes (DEFAULT is read-only -- nothing is written without --apply):
  (no flag)  List every change.
  --apply    Make them. Idempotent.

Run: uv run python preprocessing/fix_shared_tray_names.py            # list only
     uv run python preprocessing/fix_shared_tray_names.py --apply
"""

import argparse
from collections import defaultdict

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.loader.graph_loader import names_papyrus, same_number


def plan(db) -> tuple[list[dict], list[dict]]:
    """(node changes, tray changes) for every shared tray."""
    records, _, _ = db._run_query("""
        MATCH (e:EduceLabID)-[:ASSIGNED_TO]->(n)
        WITH e, collect(n) AS ns WHERE size(ns) > 1
        UNWIND ns AS n
        OPTIONAL MATCH (n)<-[:HAS*0..2]-(p:PHerc)
        RETURN e.uuid AS uuid, e.sheet_pherc AS sheet_pherc, e.sheet_cornice AS sheet_cornice,
               elementId(n) AS n_id, labels(n) AS n_labels, n.displayName AS n_dn,
               n.name AS n_name, n.aliases AS n_aliases,
               elementId(p) AS p_id, p.displayName AS p_dn, p.name AS p_name, p.aliases AS p_aliases
    """)
    if records is None:
        raise SystemExit("Query failed.")
    trays = defaultdict(list)
    for r in records:
        trays[r['uuid']].append(r)

    # A PHerc can sit on several shared trays (919 and 920 on two), so what to
    # remove is gathered per node across trays and written once.
    nodes, bad = {}, defaultdict(set)
    tray_changes = []
    for uuid, rows in sorted(trays.items()):
        phercs = {r['p_id']: r for r in rows if r['p_id']}
        objects = {r['n_id']: r for r in rows if 'PHerc' not in r['n_labels']}
        common = set.intersection(*(set(p['p_aliases'] or []) for p in phercs.values())) \
            if len(phercs) > 1 else set()
        sheet_pherc, changed = None, False
        for p_id, p in phercs.items():
            found = {a for a in common if not names_papyrus(a, p['p_dn'])}
            if found:
                sheet_pherc = p['p_name'] if p['p_name'] in found else sorted(found)[0]
                nodes[p_id] = (uuid, p['p_dn'], p['p_name'], p['p_aliases'])
                bad[p_id] |= found
                changed = True
        for n_id, n in objects.items():
            found = {a for a in [*(n['n_aliases'] or []), n['n_name']] if a and not same_number(a, n['n_dn'])}
            if found:
                nodes[n_id] = (uuid, n['n_dn'], n['n_name'], n['n_aliases'])
                bad[n_id] |= found
                changed = True
        names = {n['n_name'] for n in objects.values()}
        sheet_cornice = names.pop() if changed and len(names) == 1 else None
        update = {}
        if sheet_pherc and not rows[0]['sheet_pherc']:
            update['sheet_pherc'] = sheet_pherc
        if sheet_cornice and not rows[0]['sheet_cornice']:
            update['sheet_cornice'] = sheet_cornice
        if update:
            tray_changes.append({'uuid': uuid, **update})

    node_changes = [
        {'uuid': uuid, 'id': node_id, 'displayName': dn, 'remove': sorted(bad[node_id]),
         'aliases': [a for a in (aliases or []) if a not in bad[node_id]],
         'name': dn if name in bad[node_id] else name}
        for node_id, (uuid, dn, name, aliases) in nodes.items()
    ]
    return node_changes, tray_changes


def show(node_changes, tray_changes):
    for c in node_changes:
        print(f"  {c['uuid'][:8]}  {c['displayName']!r:<30} remove {c['remove']}")
    for t in tray_changes:
        print(f"  {t['uuid'][:8]}  EduceLabID  set {({k: v for k, v in t.items() if k != 'uuid'})}")
    print(f"\n{len(node_changes)} node(s) to clean, {len(tray_changes)} tray(s) to record names on.")


def apply(db, node_changes, tray_changes):
    for c in node_changes:
        records, _, _ = db._run_query("""
            MATCH (x) WHERE elementId(x) = $id
            SET x.aliases = $aliases, x.name = $name
            RETURN count(x) AS n
        """, id=c['id'], aliases=c['aliases'], name=c['name'])
        if not records or records[0]['n'] != 1:
            raise SystemExit(f"Update failed on {c['displayName']!r} ({c['uuid']}); stopping.")
    for t in tray_changes:
        db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            SET e.sheet_pherc = coalesce(e.sheet_pherc, $sheet_pherc),
                e.sheet_cornice = coalesce(e.sheet_cornice, $sheet_cornice)
        """, uuid=t['uuid'], sheet_pherc=t.get('sheet_pherc'), sheet_cornice=t.get('sheet_cornice'))
    print(f"Cleaned {len(node_changes)} node(s), recorded names on {len(tray_changes)} tray(s).")


def main():
    parser = argparse.ArgumentParser(description="Move shared trays' uuid-sheet names off their nodes (#61).")
    parser.add_argument("--apply", action="store_true", help="Make the changes.")
    args = parser.parse_args()

    config.request_required()
    print(f"Target: {config.uri}")
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    print("=== ANALYZE ===")
    node_changes, tray_changes = plan(db)
    show(node_changes, tray_changes)

    if args.apply:
        print("\n=== APPLY ===")
        apply(db, node_changes, tray_changes)
    else:
        print("\n(analyze only -- re-run with --apply to write)")


if __name__ == "__main__":
    main()
