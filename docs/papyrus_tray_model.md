# What is a papyrus, what is an object (feeds #21 rework and #23)

Status: vocabulary and model agreed in discussion (2026-10-19). No code or schema
change made yet. Counts are from the dev graph on 2026-10-16/19.

## Context

The graph was built as `PHerc -> Cornice -> UUID`. The real collection doesn't
fit that:
- some objects are `PHerc -> Pezzo` or `PHerc -> Cornice -> Pezzo`;
- one UUID can cover material from several PHercs, at different levels;
- one physical papyrus can carry several numbers (renumbering);
- the PHerc slot also holds placeholders (`tavoletta`, `frammenti`,
  `Cassetto`), non-PHerc papyri and PHerc. s.n.

The pipeline UI's pages need unimaged papyri and objects too, and #23 asks for
a real object kind on each artifact.

## Three layers, only one modelled

```
Text (not modelled):      Work <- Book <- Version (A, B, ...; may be lost)
                                            ^
Ancient roll (not yet):                 Scroll  (physical original; may be lost)
                                            ^   many-to-many
Catalogue (our graph):   Papyrus (PHerc #) <- Cornice / Cass. / ... <- Pezzo
```

- A **PHerc number is a catalogue number**, generally but not always from one
  ancient scroll. One scroll can be spread over several numbers, and one number
  can hold pieces of several scrolls.
- **Scroll** means the physical ancient roll. We don't model it yet. The
  papyrologists record papyrus -> scroll links in `OtherSameScrollPapyri`.
- Author and `literary_work` on a PHerc are a flattened stand-in for the text
  layer. They stay as properties for now, but nothing new should build on them
  as if they were facts about the catalogue entry.

## Vocabulary

- **Papyrus** (UI: Papyri): the top-level catalogue entry and the UI's top
  level. It covers numbered PHercs, PHerc. s.n., two-number entries
  (`1007/1673`) and papyri whose catalogue id is not a PHerc number (`Paris 1`,
  `Haun.1`, `Joannowsky Papyrus`, `TH A 74`). `573B` and `1476B` stay separate
  catalogue numbers for now. The placeholders `tavoletta`, `frammenti` and
  `Cassetto` are not papyri.
- **Tray (imaging unit)**: the physical thing put in front of the camera: a
  cornice, a scorza, a whole cassetto, or a single piece taken out of a
  cassetto. It may hold material from zero, one or several papyri. "Tray" is
  data-layer vocabulary. Users see the tray's own label (e.g. "Cornice 1
  (Fackelmann)"), never the word. An intact papyrus imaged whole would be its
  own tray, with its UUID on the PHerc node. None exists yet: the 651 "Not
  unrolled" papyri have no UUIDs.
- **EduceLabID (UUID)**: the identifier of a tray, assigned at imaging time.
  It names a physical object, not a scan, so imaging a tray again adds datasets
  under the same UUID. A tray that has never been imaged has no UUID.
- **Object**: one Cornice/Pezzo node, i.e. one papyrus's material at one place.
  There is one node per papyrus, `Cass.` nodes included. When several papyri
  share a tray, each has its own node and the nodes share the tray's UUID.
- **Pezzo**: a piece on a tray, belonging to one papyrus. Usually the tray is
  above the pezzo. In PHerc 118a, uniquely, each tray holds exactly one pezzo, so
  the trays are referred to as "PHerc 118a, Pezzo N".
- **Fragment**: a region of visible text within a pezzo. Out of scope.
- **Method** (Fackelmann, Osloense): the unwrapping method used on a tray. It
  is part of the tray's identity: Cornice `1`, `1 (Fackelmann)` and
  `1 (Osloense)` of one papyrus are three different trays.
- **Cassetto**: a large wooden box of assorted, often unidentified fragments
  and sometimes unrolled chunks. It is a storage location, not a tray and not
  a node. Most cassetto material was taken out and imaged piece by piece (e.g.
  `571 / Cass. 31`). Unconserved cassetti may be imaged whole (`Cass. 51`, as
  two images (A) right and (B) left).
- **Cassetto letters** (`Cass. 43 (A)`, `(B)`, ...): each letter is its own
  tray with its own UUID. Usually the cassetto was imaged again after fragments
  were moved. Sometimes the letter marks a part of the drawer (Cass. 51). Treat
  each as a separate tray, and group them in the UI by the shared `Cass. N`.
- **`REPLACES`**: one tray was accidentally imaged under two UUIDs. The later
  one is used from then on, and the earlier one is retired.

Relations between papyri, from the papyrologists' free-text columns in the
metadata CSV (stored today as plain string properties, not edges):

| Relation | Meaning | Source column | Rows |
|---|---|---|---|
| Stored with | different papyri kept on one tray | `StoredWithPHercNum` | 193 |
| Known as | one papyrus under several numbers (renumbering) | `PreviouslyKnownAs` / `CurrentlyKnownAs` / `SeeAlsoPHerc` | 30 / 19 / 3 |
| Same scroll as | different numbers, pieces of one ancient roll | `OtherSameScrollPapyri` | 191 |

A shared UUID means **shared tray**, nothing more. Papyri on one tray are
related only through that tray. E.g. 221, 465 Pz 2, 466, 467 Pz 1 and 1081 all
sit on Cornice 1 (Fackelmann), UUID `02160e53`, but they are not the same
scroll. No model should ever merge papyri or objects by UUID.

## How the model maps onto the graph

No new node types. The EduceLabID node already is the tray.

- `EduceLabID -[:ASSIGNED_TO]-> (Cornice|Pezzo)` means "this papyrus's
  material is on this tray". A shared tray is one EduceLabID with several
  `ASSIGNED_TO` edges.
- `Dataset -[:BELONGS_TO]-> EduceLabID` means "this dataset images this tray".
  A capture that holds two trays in one view belongs to both (see 76 Cr 05
  below).
- A tray's **kind** (cornice, scorza, cassetto piece, whole cassetto, ...),
  **method** and **display label** are worked out from the names of the nodes
  it is assigned to, the way the UI's `naming.py` already does. None of them is
  stored. Display names stay untouched, since they are the CSV join key.

Checked against the 28 shared UUIDs:
- 22 are assigned to nodes that all have the same name, so the label is clear.
- `02160e53` is assigned to a cornice and two pezzi (`1 (Fackelmann)`,
  `465/2`, `467/1`). Use the cornice-level name.
- `a7bee49b`, `caa97a09`, `614efdb7` (72, 1362, 1363) are each assigned to the
  papyrus node and to its `Cass.` node. These are pieces taken out of a
  cassetto and imaged alone, i.e. single-item trays. The UUID belongs on the
  `Cass.` node, and the papyrus-level assignment should go (#40).
- `85e4072e` is assigned to `1 (Oslo)` (1208) and `1 (Osloense)` (1691).
  `Osloense` is correct. Fix it in the source sheet.
- `4456f59f` is assigned to `2 (Osloense)` (1157) and `1 (Osloense)` (1191).
  Correct: one Oslo tray holding 1157's second cornice and one piece of 1191
  laid over it. Each papyrus numbers its own cornici (Q-03, closed).

The placeholder PHercs (`tavoletta` 135 cornici, `Cassetto` 5, `frammenti` 2)
come from the Cassetti sheet. There, each row under a cassetto is one imaged
tray with its own UUID, and rows with no single PHerc number were filed under a
placeholder. In this model they are trays holding no single papyrus's
material, so they belong in a tray view, not the papyrus list.

## What the UI shows

- **Papyri list**: one row per papyrus, placeholders left out (what `GET
  /pherc` does now with its stopgap filter).
- **Papyrus page**: its objects (Cornice/Pezzo nodes), imaged or not. Each
  imaged object shows its tray label and, if the tray is shared, "shared with"
  the other papyri on it. Plus the Stored with / Known as / Same scroll as
  relations once they are edges.
- **Tray view** (for the computer scientists, keyed by UUID): today's
  per-UUID `GET /artifacts`. Each row needs the derived label and kind, and
  must include the placeholder trays.

## Decisions and follow-ups

1. Derive kind, method and tray label in the API from the node names. Nothing
   stored, no new labels. This covers #23's first ask.
2. Drop the papyrus-level `ASSIGNED_TO` for 72, 1362 and 1363 (#40). The
   double assignment comes from the two sources disagreeing. The metadata CSV
   puts these UUIDs on the papyrus row (the only 3 of 1871 papyrus rows with a
   UUID), and the uuid sheet puts them on the `Cass.` row. The metadata rows
   are the ones to correct.
3. **PHerc 1063**: the graph is wrong to put it on tray `d5b9ebc4` with
   228/444/1073. The source sheets are right: the 1063 came from a typo in the
   loader's hard-coded list. Fixed in #59.
4. **76 Cr 05 Left/Right**: the whole-cornice spectral scan `ce015560`
   (`PHerc0076Cr05 LR (Fa...`) shows both trays, so it belongs to both Left
   (`10517d86`) and Right (`c5ca1b3a`). This is the single `sample uuid 2` link
   dropped in the 2026 CSVs (`data_review_notes.md` §5). Restore it with a
   hand-kept list of extra links that `scan_loader` re-applies after
   `--replace`, like the excluded-test-scans list. Photogrammetry was captured
   per tray and needs nothing. Done in #43 (`input_data/extra_scan_links.csv`).
5. **Relation edges** (own issue): parse the three relations above into
   `STORED_WITH`, `KNOWN_AS` and `SAME_SCROLL_AS` edges between papyri. Parse
   conservatively (hand-entered text: `cr 1`, `?`, `olim`, `465/II` vs `465/2`,
   typos like `1839`). Anything that doesn't match an existing node goes to
   `data_review_notes.md`. `SAME_SCROLL_AS` stands in for the Scroll node: a
   later Scroll node can replace each connected group of these edges with one
   hub.
6. Add the parts of two-number papyri to `aliases`, so that "1673" finds
   `1007/1673`. Done in #45.
7. Cassetto pieces split off as their own PHercs (`1132 A-B-C`, `1135 A`,
   `955 A-B`, `1256 A I-II`, `PHerc. 133 A IV gamma`): 1132 A-B-C is rolled
   pieces of 1132 kept in Cass. 60, catalogued only in the Cassetti sheet, and
   the base numbers all exist as PHercs. Attach these to their base papyrus.
   `573B` and `1476B` stay separate.
8. Out of scope: the Pezzi sheet of the metadata spreadsheet (ignore it),
   fragments, the Scroll and Text layers.

## Open questions for the papyrologists

Tracked, with working assumptions, in [open_questions.md](open_questions.md) as
Q-03 and Q-08. Definitions are in [glossary.md](glossary.md).

1. ~~**`4456f59f`**: which cornice of 1157 is on this tray?~~ Answered from the
   data (Q-03): 1157's `2 (Osloense)`, stored with one piece of 1191.
2. Confirm that `1135 A`, `955 A-B`, `1256 A I-II` and `PHerc. 133 A IV gamma`
   are pieces of 1135/955/1256/133, like 1132 A-B-C.

## Verification (once implemented)

- Every Cornice/Pezzo node gets exactly one derived kind. Count per kind, and
  diff against the UI's `naming.object_type()` on the same rows.
- Every shared UUID gets one tray label, except the cases listed above.
- After follow-up 2, no PHerc node carries an EduceLabID, except an intact
  papyrus imaged whole (none yet).
- After follow-up 4, scan `ce015560` is listed under both 76 Cr 05 Left and
  Right.
