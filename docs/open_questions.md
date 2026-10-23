# Open questions

One list of the questions we're waiting on, mostly for the papyrologists, plus
the **assumption** we work under until each one is answered. A question never
blocks work. We pick a sensible assumption, record it here, build on it, and
correct things once the answer comes back.

The detailed evidence stays where it already lives (`data_review_notes.md`,
`graph_data_audit.md`, `papyrus_tray_model.md`, GitHub issues). This file is
the index of what's still open and what each open item affects. Terms are
defined in [glossary.md](glossary.md).

## How to use this file

- **Add** a question as the next `Q-NN`, with who should answer it, the
  assumption we're using, and what depends on that assumption.
- **Mark code that relies on an assumption** with a comment naming the
  question, e.g. `# Assumption Q-14: ...`. When the answer arrives,
  `grep -rn "Q-14"` finds everything to revisit.
- **Status** goes through these steps:
  - `open`: assumption in use, not asked yet
  - `sent YYYY-MM-DD`: sent to the answerer
  - `answered YYYY-MM-DD`: answer recorded, follow-up not done yet
  - `closed YYYY-MM-DD`: the answer matched the assumption, or the
    follow-up fix is done
- **When answered:** write the answer under the entry. If it differs from the
  assumption, list what was corrected (PR, deploy-log entry, data fix). Keep
  closed entries here as a record of decisions.

Answerers, named by role, never by person (this repo is public):
**Papyrologists**; **Technical lead** (pipeline, imaging data, UI); **Imaging
team** (scan naming and capture).

## Index

| ID | Question (short) | Answerer | Status | Affects |
|---|---|---|---|---|
| [Q-01](#q-01) | Is a shared UUID a shared tray, not one object? | Papyrologists | closed 2026-10-22 | model, `/artifacts`, #47 |
| [Q-02](#q-02) | Is an s.n. aggregator a separate papyrus from its members? | Papyrologists | open | #44 relation edges |
| [Q-03](#q-03) | Which cornice of 1157 is on tray `4456f59f`? | Papyrologists | open | #42 |
| [Q-04](#q-04) | `1 (Oslo)` on 1208 is `1 (Osloense)`? | Papyrologists | closed 2026-10-22 | #42, naming `method` |
| [Q-05](#q-05) | Is PHerc 1063 on tray `d5b9ebc4`, or is it 1073? | Papyrologists | closed 2026-10-22 | #59 |
| [Q-06](#q-06) | Are the loader's hard-coded UUID cases still needed? | Technical lead | open | `metadata_loader.py` |
| [Q-07](#q-07) | 72 / 1362 / 1363: is the UUID on the `Cass.` node, not the papyrus? | Papyrologists | open (agreed internally) | #40 |
| [Q-08](#q-08) | Are `1135 A`, `955 A-B`, `1256 A I-II`, `133 A IV gamma` pieces of their base papyrus? | Papyrologists | open | #46 |
| [Q-09](#q-09) | Is the `Cassetto` placeholder a whole cassetto for Cass. 52 and 98 too? | Papyrologists | open | #23 `kind` |
| [Q-10](#q-10) | Label form for a whole cassetto | Technical lead | open | #23 `label`, UI |
| [Q-11](#q-11) | Is `0927 bis` the same papyrus as `927bis`? | Papyrologists | open | aliases, `/pherc` list |
| [Q-12](#q-12) | Do the cornice rows after the `PHerc 199-…jpg` overflow row belong to 199? | Papyrologists | open | metadata load |
| [Q-13](#q-13) | Which cornice of PHerc 21 is scan `PHerc0021Cr01`? | Papyrologists / Imaging team | open | 1 stranded scan |
| [Q-14](#q-14) | Scan names written `Cn`: is `Cn` the same as `Cr` (Cornice)? | Imaging team | open | 12 stranded scan UUIDs |
| [Q-15](#q-15) | Is the excluded test-scan list complete? | Technical lead / Imaging team | open | coverage report |
| [Q-16](#q-16) | Delete or mint UUIDs for the 433 failed outputs? | Technical lead | open | processed datasets |
| [Q-17](#q-17) | 176 Cr 3 / Cr 10 swap: does `negatives.csv` agree? | Technical lead | open | #49 |
| [Q-18](#q-18) | What does a pipeline on a multi-papyrus tray belong to? | Technical lead | open | #15, pipeline UI list |
| [Q-19](#q-19) | Are `folded sheet`, `frammento di papiro ercolanese`, `s.n. frammenti 1-2` loose material, not papyri? | Papyrologists | open | #23 `kind`; `GET /pherc` (unchanged until answered) |

---

## Q-01

**Is a shared UUID a shared tray, never the same object?** 28 EduceLabIDs are
assigned to several nodes, e.g. `02160e53` to Cornice 1 (Fackelmann) of 221,
466, 1081 and Pezzi 465/2, 467/1.

- **Answerer:** Papyrologists. Status: closed 2026-10-22.
- **Answer:** yes. The EduceLabID is an identifier on the computer-science
  side, so what it means is ours to define: a shared UUID means the papyri
  share a tray and nothing more. Each keeps its own node, and nothing is
  merged by UUID.
- **Affects:** `docs/papyrus_tray_model.md`, `GET /artifacts` (one row per
  UUID), #47.
- **Source:** `data_review_notes.md` §1; `graph_data_audit.md` §2.

## Q-02

**Is an s.n. aggregator (e.g. `4 PHerc. s.n.`) its own papyrus, or only a label
for the bundle 1832–1835?**

- **Answerer:** Papyrologists. Status: open.
- **Assumption:** it's a separate papyrus node. We don't infer that the
  aggregator contains its members.
- **Affects:** #44 (`KNOWN_AS` edges would link aggregator and members).
- **Source:** `data_review_notes.md` §1 B1. Note the `1839` typo there (members
  are 1829–1831).

## Q-03

**Tray `4456f59f`: the uuid sheet puts it on 1191 `1 (Osloense)` and 1157
`2 (Osloense)`. In the metadata sheet, 1157's `2 (Osloense)` is marked in
red, but the uuid sheet lists only `1 (Osloense)` for it. Which cornice of
1157 is on this tray?**

- **Answerer:** Papyrologists. Status: open.
- **Assumption:** leave the graph as loaded (1157 `2 (Osloense)`).
- **Affects:** #42 (source-sheet fix).
- **Source:** `papyrus_tray_model.md` open question 1;
  `data_review_notes.md` §1 B3.

## Q-04

**Tray `85e4072e` is on 1208 `1 (Oslo)` and 1691 `1 (Osloense)`. Is `Oslo` a
spelling variant of `Osloense`?**

- **Answerer:** Papyrologists. Status: closed 2026-10-22.
- **Answer:** yes. The naming module reads `(Oslo)` as method `Osloense`.
  1208's entry in the source sheet is still to be fixed (#42).
- **Affects:** #42; #23 `method`.
- **Source:** `papyrus_tray_model.md` follow-up list (the 85e4072e item);
  `data_review_notes.md` §1 B3, §3.

## Q-05

**Is PHerc 1063 on tray `d5b9ebc4` (with 228, 444), or should it be 1073?** The
loader's hard-coded list says 1063, and the metadata CSV says 1073.

- **Answerer:** the source data. Status: closed 2026-10-22.
- **Answer:** 1073. The uuid sheet lists the tray as "228, 444, 1073", and
  the metadata CSV puts the UUID on those three, each naming the other two
  as stored with it. "1063" was a typo in the loader's hard-coded list. It
  was fixed there, and the phantom cornice under 1063 was removed (#59).
- **Affects:** #59.
- **Source:** `data_review_notes.md` §2; `papyrus_tray_model.md` decision 3.

## Q-06

**Are the hard-coded UUID cases in `metadata_loader.py` (`02160e53`,
`d5b9ebc4`, `6c88ad2a`, and the three `Scorza` pezzi) still needed?**

- **Answerer:** Technical lead. Status: open.
- **Assumption:** keep them until a reload without them is diffed against the
  graph.
- **Affects:** `metadata_loader.py`.
- **Source:** `data_review_notes.md` §2.

## Q-07

**72, 1362 and 1363 each have their UUID on both the papyrus and its `Cass.`
node. Is the UUID the `Cass.` piece's alone?**

- **Answerer:** Papyrologists. Status: open (agreed internally 2026-10-19).
- **Assumption:** yes. These are single pieces taken out of a cassetto. The
  metadata CSV rows are wrong, and the papyrus-level `ASSIGNED_TO` should go.
- **Affects:** #40.
- **Source:** `papyrus_tray_model.md` decision 2; `data_review_notes.md` §4;
  `graph_data_audit.md` §2.

## Q-08

**Are `1135 A`, `955 A-B`, `1256 A I-II` and `PHerc. 133 A IV gamma` pieces of
1135 / 955 / 1256 / 133, like `1132 A-B-C` is of 1132?**

- **Answerer:** Papyrologists. Status: open.
- **Assumption:** yes. Attach each to its base papyrus.
- **Affects:** #46.
- **Source:** `papyrus_tray_model.md` open question 2.

## Q-09

**Are all trays under the `Cassetto` placeholder whole cassetti?** The model
doc names `Cass. 51 (A)/(B)` as a cassetto imaged whole. The same placeholder
also holds `Cass. 52 (A)/(B)` and `Cass. 98`. Other cassetto trays sit under
`tavoletta` (135), and their letters can mean a later re-imaging instead.

- **Answerer:** Papyrologists. Status: open (raised 2026-10-22).
- **Assumption:** yes. All five get kind `whole_cassetto`, and `tavoletta`
  trays get kind `tavoletta`. If 52 or 98 turn out to be tavolette, that's a
  source-sheet fix, not a code rule.
- **Affects:** #23 `kind` (`naming.object_kind`).
- **Source:** `.claude/plans/23_object_kind.md`.

## Q-10

**How should a whole cassetto be labelled: `Cassetto 51 (A)`, or the UI's
current `Tavoletta A, Cassetto 51`?**

- **Answerer:** Technical lead. Status: open (raised 2026-10-22).
- **Assumption:** `Cassetto 51 (A)`.
- **Affects:** #23 `label` (`naming._drawer_object`); the pipeline UI's
  artifact list.

## Q-11

**Is `0927 bis` (a metadata row with no cornici) the same papyrus as
`927bis`?**

- **Answerer:** Papyrologists. Status: open.
- **Assumption:** treat them as separate nodes, as loaded. No merge.
- **Affects:** `GET /pherc` (lists both); aliases.
- **Source:** `data_review_notes.md` §8.

## Q-12

**In the metadata CSV, a filename overflowed into the PHerc column
(`PHerc 199-Cornice 2-…jpg`). Do the cornice rows under it belong to
PHerc 199?**

- **Answerer:** Papyrologists. Status: open.
- **Assumption:** loaded as they are. Not attached to 199.
- **Affects:** metadata load.
- **Source:** `data_review_notes.md` §8 (cell-overflow rows).

## Q-13

**Scan `PHerc0021Cr01` names a plain Cornice 1, but PHerc 21 has
`1 (Osloense)` and `1 (Fackelmann)`. Which one is it?**

- **Answerer:** Papyrologists or Imaging team. Status: open.
- **Assumption:** none. The scan stays on its unassigned UUID, so no artifact
  page can reach it.
- **Affects:** 1 stranded scan.
- **Source:** `graph_data_audit.md` §1.

## Q-14

**12 scan UUIDs are named with `Cn` instead of `Cr` (`PHerc339Cn01`–`Cn06`,
`PHerc1413Cn01`–`Cn04`, `PHerc0197Cn02`, `PHerc1416Cn05`). Is `Cn` a typo for
Cornice?**

- **Answerer:** Imaging team. Status: open.
- **Assumption:** yes, but nothing has been fixed yet. Those scans stay
  unreachable until the uuid sheet is fixed.
- **Affects:** 12 of the 16 EduceLabIDs holding stranded scans.
- **Source:** `graph_data_audit.md` §1.

## Q-15

**Is the excluded test-scan list complete?** It was built from path patterns,
so a test run with a normal-looking path would be missed.

- **Answerer:** Technical lead or Imaging team. Status: open.
- **Assumption:** complete as of 2026-10-02.
- **Affects:** scan-completeness report; `input_data/excluded_test_scans.csv`.
- **Source:** `data_review_notes.md` §9.

## Q-16

**433 processed datasets from failed Processes have no `uuid`. Delete them, or
mint UUIDs for them?**

- **Answerer:** Technical lead. Status: open.
- **Assumption:** leave them as they are. They're never archived.
- **Affects:** processed datasets; `migrate_dataset_uuids.py`.
- **Source:** `data_review_notes.md` §10.

## Q-17

**Before swapping the UUIDs of 176 Cornice 3 and Cornice 10, does
`negatives.csv` agree that the trays were mislabelled at imaging?**

- **Answerer:** Technical lead. Status: open.
- **Assumption:** none. #49 waits for this check.
- **Affects:** #49 (and the path rename tracked in acquisition-workflow
  GitLab work item 5).

## Q-18

**A pipeline on a tray shared by several papyri shows under one of them. What
is a pipeline for: the tray, or each papyrus on it?**

- **Answerer:** Technical lead. Status: open.
- **Assumption:** a pipeline is for the tray (its EduceLabID). The list shows
  one papyrus, chosen deterministically.
- **Affects:** #15; the pipeline UI's pipeline list.
- **Source:** `graph_data_audit.md` §3.

## Q-19

**Three PHerc nodes hold loose material rather than a numbered papyrus:
`folded sheet`, `frammento di papiro ercolanese` and `s.n. frammenti 1-2`.
Each holds one cassetto tray (`Cass. 116`, `Cass. 116`, `Cass.107`). Are they
loose material, like the `frammenti` placeholder, or papyri in their own
right?**

- **Answerer:** Papyrologists. Status: open (raised 2026-10-22).
- **Assumption:** loose material, so their trays get kind `frammenti` and
  the PHerc nodes themselves `kind: null`, as in the pipeline UI. `GET
  /pherc` still lists them, unchanged. Dropping them from `/pherc` (which the
  UI's scroll list already does) waits for this answer.
- **Affects:** #23 `naming.is_papyrus`; a possible `GET /pherc` change.
