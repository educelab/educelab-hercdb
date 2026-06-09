"""Phase 3 migration: move PHerc/Cornice/Pezzo to the canonical-displayName +
aliases name model. See .claude/plans/name_displayname_alias_model.md.

Modes (DEFAULT is read-only analysis — nothing is written without --apply):
  (no flag)      Analyze: report null-displayName backfills, the alias build,
                 duplicate (trim-collision) groups, and residual gaps. No writes.
  --apply        Backfill displayName = coalesce(displayName, name) [trimmed],
                 set aliases = expand([displayName, name, existing aliases])
                 (Casetta synonyms included), and create the full-text index.
                 Idempotent.
  --merge-dupes  Additionally merge the duplicate groups via apoc.refactor.
                 mergeNodes (relationships combined, one survivor keeps the
                 canonical displayName + unioned aliases). REVIEW the analyze
                 output first. Run after --apply.

Reuses PhercGraphDatabaseLoader._expand_aliases so the migration and the loader
produce identical alias sets.

Run: uv run python preprocessing/migrate_name_aliases.py            # analyze only
     uv run python preprocessing/migrate_name_aliases.py --apply
     uv run python preprocessing/migrate_name_aliases.py --merge-dupes
"""

import argparse
from collections import defaultdict

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader as L

INDEX_NAME = "artifact_names"


def primary_label(labels):
    for lab in ("PHerc", "Cornice", "Pezzo"):
        if lab in labels:
            return lab
    return labels[0] if labels else "?"


def fetch(db):
    # Pull each node's parent(s) too: Cornice/Pezzo displayNames are only unique
    # WITHIN a parent PHerc, so duplicate detection must be parent-scoped (a node
    # can have multiple parents — shared cornici — so collect them all).
    records, _, _ = db._run_query("""
        MATCH (n) WHERE n:PHerc OR n:Cornice OR n:Pezzo
        OPTIONAL MATCH (parent)-[:HAS]->(n)
        RETURN elementId(n) AS element_id, labels(n) AS labels,
               n.displayName AS displayName, n.name AS name, n.aliases AS aliases,
               collect(DISTINCT elementId(parent)) AS parent_ids
    """)
    return [dict(r) for r in (records or [])]


def compute(rows):
    """For each node, derive the canonical displayName and full alias set."""
    out = []
    for r in rows:
        disp = (r["displayName"] or "").strip()
        name = (r["name"] or "").strip()
        existing = [a for a in (r["aliases"] or []) if a]
        # Canonical: keep curated displayName; else fall back to name/alias.
        new_display = disp or name or (existing[0].strip() if existing else "")
        fell_back = (not disp) and bool(new_display)
        # Expand + trim + dedupe every known form (Casetta synonyms included).
        new_aliases = L._expand_aliases(r["displayName"], r["name"], *existing)
        if new_display and new_display not in new_aliases:
            new_aliases = [new_display] + new_aliases
        out.append({
            "element_id": r["element_id"],
            "label": primary_label(r["labels"]),
            "old_display": r["displayName"],
            "new_display": new_display or None,
            "new_aliases": new_aliases,
            "fell_back": fell_back,
            "parent_ids": frozenset(p for p in (r["parent_ids"] or []) if p),
        })
    return out


def find_collisions(computed):
    """Groups of >1 distinct node that are genuinely the same artifact.

    PHerc displayNames are meant to be globally unique, so PHercs group by
    name alone. Cornice/Pezzo names repeat across PHercs (every PHerc has a
    Cornice "1"), so they are duplicates only when they ALSO share the same
    parent set — otherwise they are distinct entities and must not be merged.
    """
    groups = defaultdict(list)
    for c in computed:
        if not c["new_display"]:
            continue
        if c["label"] == "PHerc":
            key = ("PHerc", c["new_display"])
        else:
            key = (c["label"], c["new_display"], c["parent_ids"])
        groups[key].append(c)
    return {k: v for k, v in groups.items() if len(v) > 1}


def analyze(rows, computed, collisions):
    null_before = sum(1 for r in rows if not (r["displayName"] or "").strip())
    residual = [c for c in computed if c["fell_back"] or not c["new_display"]]
    print("=== ANALYZE (no writes) ===")
    print(f"  total PHerc/Cornice/Pezzo nodes : {len(rows)}")
    print(f"  null displayName (to backfill)  : {null_before}")
    print(f"  duplicate groups (trim-collision): {len(collisions)} "
          f"({sum(len(v) for v in collisions.values())} nodes)")
    print(f"  residual gaps (displayName from name/alias — need curated name): {len(residual)}")

    if collisions:
        print("\n  -- duplicate groups (review before --merge-dupes) --")
        for members in sorted(collisions.values(),
                              key=lambda ms: (ms[0]["label"], ms[0]["new_display"])):
            label = members[0]["label"]
            disp = members[0]["new_display"]
            olds = [repr(m["old_display"]) for m in members]
            print(f"    [{label}] '{disp}'  <-  {len(members)} nodes, old displayNames: {olds}")

    if residual:
        print("\n  -- residual gaps (displayName fell back from name/alias) --")
        for c in sorted(residual, key=lambda x: (x["label"], x["new_display"] or "")):
            print(f"    [{c['label']}] new='{c['new_display']}'  aliases={c['new_aliases']}")


def apply_changes(db, computed):
    batch = [{"id": c["element_id"], "disp": c["new_display"], "aliases": c["new_aliases"]}
             for c in computed if c["new_display"]]
    db._run_query("""
        UNWIND $batch AS row
        MATCH (n) WHERE elementId(n) = row.id
        SET n.displayName = row.disp, n.aliases = row.aliases
    """, batch=batch)
    print(f"  applied displayName + aliases to {len(batch)} nodes")
    # Skipped nodes (no derivable name) stay untouched and are listed by analyze.
    skipped = [c for c in computed if not c["new_display"]]
    if skipped:
        print(f"  WARNING: {len(skipped)} nodes had no derivable name and were left as-is")


def create_index(db):
    db._run_query(f"""
        CREATE FULLTEXT INDEX {INDEX_NAME} IF NOT EXISTS
        FOR (n:PHerc|Cornice|Pezzo) ON EACH [n.displayName, n.aliases]
    """)
    print(f"  ensured full-text index '{INDEX_NAME}' on displayName + aliases")


def merge_dupes(db, collisions):
    if not collisions:
        print("  no duplicate groups to merge")
        return
    for members in collisions.values():
        label = members[0]["label"]
        disp = members[0]["new_display"]
        # Survivor = first node in the list under apoc mergeNodes. Put the node
        # that already had a real displayName first so the curated/metadata-rich
        # node survives and the phantom (null-displayName, usually one stray
        # relationship) is merged into it — never the other way around.
        ordered = sorted(members, key=lambda m: m["old_display"] is None)
        ids = [m["element_id"] for m in ordered]
        union = []
        for m in ordered:
            for a in m["new_aliases"]:
                if a not in union:
                    union.append(a)
        db._run_query("""
            MATCH (n) WHERE elementId(n) IN $ids
            WITH collect(n) AS ns
            CALL apoc.refactor.mergeNodes(ns, {properties:'discard', mergeRels:true}) YIELD node
            SET node.displayName = $disp, node.aliases = $union
            RETURN node
        """, ids=ids, disp=disp, union=union)
        print(f"    merged [{label}] '{disp}' ({len(ids)} nodes)")


def main():
    parser = argparse.ArgumentParser(description="Name-model migration (analyze by default).")
    parser.add_argument("--apply", action="store_true",
                        help="Backfill displayName + aliases and create the index.")
    parser.add_argument("--merge-dupes", action="store_true",
                        help="Merge duplicate (trim-collision) node groups. Run after --apply.")
    args = parser.parse_args()

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    rows = fetch(db)
    computed = compute(rows)
    collisions = find_collisions(computed)

    analyze(rows, computed, collisions)

    if args.apply:
        print("\n=== APPLY ===")
        apply_changes(db, computed)
        create_index(db)

    if args.merge_dupes:
        print("\n=== MERGE DUPLICATES ===")
        merge_dupes(db, collisions)

    if not args.apply and not args.merge_dupes:
        print("\n(analyze only — re-run with --apply to write, then --merge-dupes to merge)")


if __name__ == "__main__":
    main()
