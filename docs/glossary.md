# Glossary

The words we use for the collection, the graph and the pipeline. The
collection terms follow the model agreed in
[papyrus_tray_model.md](papyrus_tray_model.md). Where a definition rests on
an unanswered question, it links to [open_questions.md](open_questions.md).

Italian terms are kept as the catalogue uses them. The plural is in brackets.

## The collection

**Papyrus** (UI: Papyri). A top-level catalogue entry and the UI's top level.
Usually a PHerc number, but also PHerc. s.n., two-number entries
(`1007/1673`), and papyri whose id isn't a PHerc number (`Paris.1`,
`Haun.1`, `Joannowsky Papyrus`, `TH A 74`). In the graph, a `PHerc` node,
except for the placeholders.

**PHerc** (*Papyrus Herculanensis*). A catalogue number in the Herculaneum
collection. It is generally, but not always, one ancient scroll: one scroll
can be spread over several numbers, and one number can hold pieces of
several scrolls.

**Scroll**. The physical ancient roll. Not modelled yet. The papyrologists
record which papyri come from the same scroll (see *Same scroll as*).

**s.n.** (*sine numero*). An unnumbered papyrus, usually named after where
it's kept, e.g. `PHerc. s.n. Cass LI`, `Cass. 78 s.n. C`.

**Two-number papyrus**. One papyrus catalogued under two numbers, written
with a slash: `1007/1673`, `152/157`.

**bis, letter suffixes**. `927bis`, `118a`, `118b`, `573B` are separate
catalogue numbers, each its own papyrus. See [Q-11](open_questions.md#q-11).

**Cornice** (cornici). A frame holding unrolled material from a papyrus.
Usually numbered (`1`, `2`) and sometimes tagged with a method
(`1 (Osloense)`). In the graph, a `Cornice` node under a `PHerc`.

**Scorza** (scorze). The outer layers peeled off a scroll, mounted on their
own tray, e.g. `Scorze da 90 a 223`.

**Pezzo** (pezzi). A piece on a tray, belonging to one papyrus. Usually it
sits under a cornice, sometimes directly under the papyrus. In PHerc 118a
each tray holds exactly one pezzo, so the trays are called "PHerc 118a,
Pezzo N".

**Fragment**. A region of visible text within a pezzo. Out of scope for the
graph.

**Cassetto** (cassetti). A large wooden storage box of assorted, often
unidentified fragments, and sometimes unrolled chunks. It's a storage
location, not a tray and not a node. Written `Cass. N` in the sheets
(variants: `Cass.N`, `cass.`, `Cassetta`, Roman numerals as in
`Cass CXIV`).

**Cassetto piece**. One piece taken out of a cassetto and imaged on its own,
e.g. `571 / Cass. 31`.

**Whole cassetto**. A cassetto imaged as a whole, e.g. `Cass. 51 (A)` and
`(B)`. See [Q-09](open_questions.md#q-09).

**Cassetto letters**. `Cass. 43 (A)`, `(B)`, …: each letter is its own tray
with its own UUID. Usually the cassetto was imaged again after fragments
were moved. Sometimes the letter marks a part of the drawer. Group them by
the shared `Cass. N`.

**Tavoletta** (tavolette). A tray of cassetto material that belongs to no
single papyrus. The Cassetti sheet files these under the placeholder PHerc
`tavoletta`.

**Frammenti**. Loose material that belongs to no single papyrus, filed under
placeholder PHercs such as `frammenti` and `folded sheet`.

**Placeholder PHerc**. A `PHerc` node that isn't a papyrus: `tavoletta`,
`Cassetto`, `frammenti`. They exist because the uuid sheet needs a value in
its PHerc column. They're left out of the papyrus list (`GET /pherc`).

**Method**. The unwrapping method used on a tray: **Osloense** (also written
`Oslo`, see [Q-04](open_questions.md#q-04)) or **Fackelmann**. It's part of
the tray's identity: Cornice `1`, `1 (Fackelmann)` and `1 (Osloense)` of one
papyrus are three different trays.

**Disegni**. Historical drawings of papyri, stored as `Disegni` nodes.

### Relations between papyri

From the papyrologists' free-text columns in the metadata CSV. Stored today
as string properties. #44 will turn them into edges.

| Relation | Meaning | Column |
|---|---|---|
| **Stored with** | different papyri kept on one tray | `StoredWithPHercNum` |
| **Known as** | one papyrus under several numbers (renumbering) | `PreviouslyKnownAs`, `CurrentlyKnownAs`, `SeeAlsoPHerc` |
| **Same scroll as** | different numbers, pieces of one ancient roll | `OtherSameScrollPapyri` |

## Imaging units and identifiers

**Tray** (imaging unit). The physical thing put in front of the camera: a
cornice, a scorza, a whole cassetto, or a single cassetto piece. It may hold
material from zero, one or several papyri. "Tray" is data-layer vocabulary.
Users see the tray's label, never the word.

**Object**. One `Cornice` or `Pezzo` node, i.e. one papyrus's material in one
place. When several papyri share a tray, each has its own object node, and
the nodes share the tray's UUID.

**EduceLabID / UUID**. The identifier of a tray, assigned at imaging time. It
names a physical tray, not a scan, so imaging the tray again adds datasets
under the same UUID. A tray that was never imaged has no UUID.

**Shared UUID / shared tray**. One EduceLabID assigned to several nodes (28
on the graph). It means the papyri share a tray, nothing more. Never merge
papyri or objects by UUID. See [Q-01](open_questions.md#q-01).

**`REPLACES`**. When one tray was accidentally imaged under two UUIDs, the
newer UUID `REPLACES` the older one. Only the newer one is assigned to the
artifact. Dataset queries walk the chain so older scans still count.

**Retired**. An EduceLabID dropped without a successor (`retired = true`,
plus `retired_reason`).

**Kind, label** (derived, #23). Worked out in the API from node names, never
stored. **Kind** is one of: `papyrus`, `cornice`, `scorza`, `pezzo`,
`cassetto_piece`, `whole_cassetto`, `tavoletta`, `frammenti`. **Label** is the
readable name, e.g. "PHerc. 90, Scorze da 90 a 223".

## Names in the graph

**displayName**. The one canonical name on every PHerc/Cornice/Pezzo, and the
only one shown to users. It's also the **join key** between the uuid sheet,
the metadata CSV, the scan CSVs and the graph, so never rename a node to tidy
it up.

**aliases**. Every known form of a node's name (displayName, uuid-sheet name,
cassetto synonyms, spelling variants). Used only to resolve input to a node,
never shown.

**Artifact** (API). A PHerc, Cornice or Pezzo, as served by `/artifacts`.

**Resolve**. Fuzzy-match a noisy name to ranked candidate nodes (`GET
/resolve`). Every other endpoint matches displayName exactly.

## Data and processing

**Raw dataset**. A scan attached to an EduceLabID by `BELONGS_TO`:
**FlatbedScan**, **PGSRaw** (photogrammetry) or **SpectralRaw** (spectral
imaging).

**Processed dataset**. A pipeline output, attached to a Process by `OUTPUT`
rather than to an EduceLabID: **PGSProcessed**, **SpectralProcessed**,
**Registered** (PGS and spectral aligned) and **WebProcessed** (for web
viewing).

**Complete**. For a raw scan, `complete == "True"` *and* zero missing,
zero-byte, short and bad-format files (stricter than the CSV flag). For a
processed dataset, its Process finished.

**Released**. A dataset's publish flag (0.3.9). The flag records who set it
and when.

**Pipeline**. One submission of processing for a tray, keyed by
`pipeline_id` (the acquisition workflow's `uber_job_id`). It carries the
pipeline code's `version`.

**Process** (stage). One step of a pipeline: **PGS**, **SPEC**, **REG**
(registration) or **WEB** (webify). It has a status of `submitted`,
`archiving`, `completed` or `failed`, plus its Slurm job id. Stored in Neo4j
as `stage` and called `proc_type` in Python/REST.

**Work-list**. The complete raw scans still waiting for a given process type
(`GET /datasets/{proc_type}/unprocessed`). The unattended dispatcher
(auto-queue) reads it.

**Ambiguous** (work-list). A complete scan the dispatcher skips, e.g. because
it's assigned to more than one papyrus.

**Excluded scan**. A test-run raw scan detached from its artifact and marked
`excluded = true`, so it doesn't count toward coverage.

## Systems

**Dev / prod**. Dev Neo4j and REST on `.43` (overwritten nightly by a `.41`
snapshot). Production on `.41`. Develop and test on dev only.

**acquisition-workflow**. The sibling repo that runs imaging pipelines on the
cluster. It writes to the graph only through `HercClient`.

**Pipeline UI**. The web front end (`educelab-hercdb-pipeline-ui`, heading
for its `ui-redesign` branch). It reads the REST API.
