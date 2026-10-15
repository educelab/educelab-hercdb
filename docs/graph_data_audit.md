# Graph data audit — open questions

**2026-09-17 (not started — parked deliberately)**

A read-only audit of the **live graph**, as opposed to `docs/data_review_notes.md`,
which reviews the **CSVs going in**. Most of what turned up here is already known on
the CSV side; this file records what it looks like in the database today, how much data
it affects, and what the portal does with it.

Nothing here has been acted on. **Renaming is the obvious fix for most of it and the
wrong thing to reach for first** — display names are the join key between the uuid
sheet, the metadata CSV, the scan CSVs and the graph, so a rename that tidies one makes
the others miss. Resolve what the correct name *is* with a papyrologist before touching
anything.

No code change is needed for any of this. The queries below are read-only and safe to
re-run to see whether the numbers have moved.

---

## 1. EduceLabIDs with no artifact (133)

```
total EduceLabID nodes                     3812
  no ASSIGNED_TO edge                       133
    retired or superseded                     3
    genuine gaps                            130   = db.find_unassigned_educelabids()
      of those, holding scans                16   ← the ones that matter
      bare, nothing attached                117
scans stranded on them                       46
pipelines on them                             0   ← nothing has been processed from one
```

The 117 bare ones are uuid-sheet rows with blank `PHerc`/`Pezzo` columns — already
covered in `data_review_notes.md` §7, which notes `metadata_loader.py` creates the
EduceLabID with no `ASSIGNED_TO` in that case. They hold nothing, so they cost nothing
beyond clutter.

**The 16 that hold scans are the real finding: 46 scans that no page in the portal can
reach.** An artifact page is addressed by artifact, so a scan hanging off an
unassigned EduceLabID is not merely unnamed, it is unreachable. In every case below
**the target artifact already exists** — the scan simply never matched it.

| Cause | EduceLabIDs | Detail |
|---|---|---|
| Cornice written `Cn`, not `Cr` | 12 | `PHerc339Cn01`–`Cn06`, `PHerc1413Cn01`–`Cn04`, `PHerc0197Cn02`, `PHerc1416Cn05`. PHerc 339 has Cornici 1–6 and PHerc 1413 has 1–4, so these had somewhere to land. `data_review_notes.md` §5 already flags `MVDaily_20220930/PHerc1670Cn01` as the same pattern |
| Truncated name | 2 | `PHerc0494CrFackelman` (missing the final `n`), `PHerc1784Cr01 (Facke` (cut mid-word) |
| Cornice name mismatch | 1 | `PHerc0021Cr01`. PHerc 21 exists, but its cornici are `1 (Osloense)`, `1 (Fackelmann)`, `2 (Osloense)`, `3 (Osloense)` — there is no plain `1`, so this is a question about which one it is, not a typo |
| Test data | 1 | `PHerctestCrtest` |

The `Cn` group is the one worth resolving first: 12 of 16, one consistent cause, and
the destination is unambiguous.

```cypher
// The 16 and what they hold
MATCH (e:EduceLabID) WHERE NOT (e)-[:ASSIGNED_TO]->()
MATCH (e)<-[:BELONGS_TO]-(d)
RETURN e.uuid AS uuid, collect(labels(d)[0] + ': ' + d.path) AS scans
```

---

## 2. EduceLabIDs assigned to several nodes (28) — mostly correct

Worth writing down because it **looks** like corruption and is not.

```
EduceLabIDs with >1 ASSIGNED_TO             28
  spanning 2–5 PHercs                       25   ← one scan, several fragments: correct
  spanning 1 PHerc                            3   ← the actual anomaly
```

The 25 are one scan covering several physical fragments, assigned to all of them:

```
PHerc221, 465-II, 466, 1081, 467-1Cr01 (Fackelmann)
  → Cornice 1 (Fackelmann) under PHerc 221, 466, 1081
  → Pezzo 465/2, Pezzo 467/1
```

`data_review_notes.md` §1 already records the papyrologist's position (2026-05): a
shared EduceLabID reflects shared imaging provenance, not one physical object. It
documents `d4e782a9-6ff6-548e-b6fe-e63ea7058f48` — five `1 (Osloense)` cornici under
PHerc 1832–1835 plus the aggregator `4 PHerc. s.n.` — as exactly this case. **Do not
"deduplicate" these.**

The remaining 3 are assigned to both a Cornice *and* the PHerc directly above it, which
no other artifact does:

| EduceLabID | Assigned to |
|---|---|
| `a7bee49b-cca5-53dc-b7cd-82c44c49ca2a` | Cornice `Cass.7` **and** PHerc `72` |
| `caa97a09-ba6d-5ea1-ae3d-ad4a08d9a31e` | Cornice `Cass.75` **and** PHerc `1362` |
| `614efdb7-4095-56f1-b234-35b4a3bcac1a` | Cornice `Cass.75` **and** PHerc `1363` |

All three are already in `data_review_notes.md` §4 with the origin — the uuid sheet
carries a Cornice that the metadata row lacks, so the loader creates the Cornice from
the uuid sheet — and all three end "Confirm intended." The audit adds only that the
double assignment is visible in the graph and that no other artifact shares the shape.

Since 0.3.7 these three name themselves from the Cornice rather than the bare PHerc
(`PHerc72 Cornice Cass.7`, not `PHerc72`), because `find_artifact_names_by_uuids` keeps
the most specific of several candidate names. That made the display deterministic; it
did not decide whether the double assignment is right.

---

## 3. A pipeline on a multi-fragment scan shows one artifact of several

Not a data problem — a consequence of §2 that someone will eventually report as a bug.

The portal's pipeline list has one `dataset_name` per row, so a pipeline whose scan
covers five fragments is displayed under one of them. Which one is deterministic
(most specific name, ties broken on the formatted string) but arbitrary in meaning:
any of the five is equally true.

Fixing it properly means the list carrying several artifacts per row, which is a
schema-shaped question about what a pipeline is *for*, not a formatting tweak. Worth
deciding before anyone hand-edits data to make the display read better.

---

## Reproducing this

All read-only:

```python
from educelab import hercdb
from educelab.hercdb import config
config.request_required()
db = hercdb.connect()

db.find_unassigned_educelabids()        # the 130
```

```cypher
// §2 — multi-assignment, and whether it spans one PHerc or several
MATCH (e:EduceLabID)-[:ASSIGNED_TO]->(n)
WITH e, collect(n) AS targets WHERE size(targets) > 1
UNWIND targets AS t
OPTIONAL MATCH (t)<-[:HAS*0..2]-(ph:PHerc)
WITH e, count(DISTINCT t) AS n_targets, count(DISTINCT ph.displayName) AS n_phercs
RETURN e.uuid, n_targets, n_phercs ORDER BY n_phercs
```
