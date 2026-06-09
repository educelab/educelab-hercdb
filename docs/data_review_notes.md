# Data review notes

**2026-06-02 (Task complete)** 

Running list of CSV anomalies and modelling questions that warrant papyrologist review. The current loaders preserve these patterns faithfully; this document is for tracking what to confirm with domain experts before any data or schema change.

CSV files referenced (current versions): `input_data/metadata_processed_20260428.csv`, `input_data/uuid_file_20260427.csv`.

---

## Section 1 — UUIDs that appear on multiple metadata rows

The same UUID appears in the `UUID` column for several `PapyrusNum` rows in `metadata_processed_*.csv`. The metadata loader creates one Cornice node per `(PapyrusNum, CorniceNum)` pair and links all of them to the same `EduceLabID`. Working assumption (per papyrologist input, 2026-05): each `(PHerc, Cornice)` pair represents a **distinct physical entity** even when they share an EduceLabID — the shared EduceLabID reflects shared imaging/dataset provenance, not a single physical object. Confirm.

### B1 — Aggregator + member rows

Same UUID appears on N member-PHerc rows and one aggregator-PHerc row. The aggregator names its members in `PreviouslyKnownAs`; each member references the aggregator in `CurrentlyKnownAs`.

**Question for papyrologists:** Is the aggregator (e.g. `4 PHerc. s.n.`) considered a separate entity from its members, or is it just a label for the bundle? Current decision: keep as separate entity, do not assume aggregator-contains-members in the graph.

#### `d4e782a9-6ff6-548e-b6fe-e63ea7058f48`

| PapyrusNum | CorniceNum | Role |
|---|---|---|
| `1832` | `1 (Osloense)` | member (`CurrentlyKnownAs` = `4 PHerc. s. n.`) |
| `1833` | `1 (Osloense)` | member |
| `1834` | `1 (Osloense)` | member |
| `1835` | `1 (Osloense)` | member |
| `4 PHerc. s.n.` | `1 (Osloense)` | aggregator (`PreviouslyKnownAs` = `PHerc. 1832, 1833, 1834, 1835`) |

#### `bd7d2420-05f8-5666-be61-9741c7e81f9a`

| PapyrusNum | CorniceNum | Role |
|---|---|---|
| `1829` | `1 (Osloense)` | member (`CurrentlyKnownAs` = `PHerc. s.n. I-III Cass. CXIV`) |
| `1830` | `1 (Osloense)` | member |
| `1831` | `1 (Osloense)` | member |
| `PHerc. s.n. I-III Cass CXIV` | `1 (Osloense)` | aggregator (`PreviouslyKnownAs` = `PHerc. 1829, 1839, 1831`) — note `1839` likely a typo for `1839`, since members are 1829/1830/1831 |

#### `a0eaa0ad-2ba6-5522-ba7d-3df26260078e`

| PapyrusNum | CorniceNum | Role |
|---|---|---|
| `1828` | `1 (Osloense)` | member (`CurrentlyKnownAs` = `PHerc. s.n. IV Cass. XCIV`) |
| `PHerc. s.n. IV Cass XCIV` | `1 (Osloense)` | aggregator (`PreviouslyKnownAs` = `PHerc. 1828`) |

#### `c5dbe037-6a66-5b8e-8494-9fb82bdb015f`

| PapyrusNum | CorniceNum | Role |
|---|---|---|
| `1827` | `1 (Osloense)` | member (`CurrentlyKnownAs` = `PHerc. s.n. Cass. LVIII`) |
| `PHerc. s.n. Cass. LVIII` | `1 (Osloense)` | aggregator (`PreviouslyKnownAs` = `PHerc. 1827`) |

### B2 — Co-located members, no aggregator

Same UUID + same Cornice number on multiple PapyrusNum rows. No aggregating row.

- `02160e53-71b8-52ba-bcd3-faf6c6917c66` — Cornice `1 (Fackelmann)` shared by `221`, `465`, `466`, `467`, `1081`
- `6c88ad2a-7a6a-5055-b832-babd9f859f37` — Cornice `1 (Fackelmann)` shared by `244`, `456`, `461`, `1603`
- `0c47b5ee-01cc-58b5-a18d-531778d34924` — Cornice `1 (Osloense)` shared by `603`, `610`, `636`
- `42e22e0e-719d-599e-b5a4-a285fe63e3eb` — Cornice `1 (Osloense)` shared by `1330`, `1401`, `1426`
- `d5b9ebc4-31a9-5368-90ac-eeb2893998db` — Cornice `1 (Fackelmann)` shared by `228`, `444`, `1073`
- `e5784861-d751-5d43-9a95-6d5d0806e053` — Cornice `1 (Osloense)` shared by `216`, `219`, `225`
- `05d85261-59a7-539d-ab38-286b7e9d0e51` — Cornice `1 (Osloense)` shared by `924`, `935`
- `0a9ffb4a-86bb-5433-adce-3f933c663736` — Cornice `1 (Osloense)` shared by `787`, `788`
- `25898393-91a1-5869-b7f9-067f56997c24` — Cornice `1 (Osloense)` shared by `1669`, `1701`
- `33b8e371-7556-5c13-95b6-704200520fbc` — Cornice `1 (Osloense)` shared by `907`, `909`
- `7c7c731b-1e4a-52aa-875a-3cc5a5dfcee8` — Cornice `1 (Osloense)` shared by `1751`, `1778`
- `7e1fbc2b-103a-5364-badf-e835000c6734` — Cornice `1 (Osloense)` shared by `1249`, `1320`
- `b433862d-22cc-5aff-8bf3-c88002bdabb4` — Cornice `1 (Osloense)` shared by `1493`, `1521`
- `ba8373a4-6e5b-51e4-b876-e594cdc18d17` — Cornice `1 (Osloense)` shared by `791`, `794`
- `bf4d41b8-c1cd-59f2-b717-6c4742cfab6a` — Cornice `1 (Osloense)` shared by `919`, `920`
- `d223f287-1103-5160-a89f-210e268a0554` — Cornice `2 (Osloense)` shared by `919`, `920`
- `d6a815e9-c543-56a8-8c68-8eae3ce58e0b` — Cornice `1 (Osloense)` shared by `747`, `757`
- `dc96f32e-933d-5b9b-a15e-ce379092e85b` — Cornice `1 (Osloense)` shared by `33`, `34`
- `f7b0d16b-e948-5a47-a51c-138c5a748826` — Cornice `1 (Osloense)` shared by `940`, `947`

### B3 — Same UUID, different Cornice numbers per PHerc

These are the most ambiguous: the same UUID is associated with **different Cornice numbers** depending on the PHerc.

- `4456f59f-24da-5e47-b451-0c460223efa4`:
    - PHerc `1157` → Cornice `2 (Osloense)`
    - PHerc `1191` → Cornice `1 (Osloense)`
    - UUID sheet has PHerc = `1157-1191`, Pezzo/Cr = `2 (oslo)`
- `85e4072e-b976-553a-b56f-fbb605d6ecf8`:
    - PHerc `1208` → Cornice `1 (Oslo)` (note: spelled `Oslo`, not `Osloense`)
    - PHerc `1691` → Cornice `1 (Osloense)`

**Question for papyrologists:** intentional, or a data-entry inconsistency?

---

## Section 2 — Hard-coded edge cases in the loader

These UUIDs are hard-coded in `src/educelab/hercdb/loader/metadata_loader.py` (around lines 294–316) and bypass the normal UUID-sheet processing. Each one attaches a single UUID across multiple PHercs because the UUID sheet alone could not express that.

| UUID | What the loader does | Notes |
|---|---|---|
| `02160e53-71b8-52ba-bcd3-faf6c6917c66` | Sets PHerc-name on `221`, `1081` and creates Cornice `1 (Fackelmann)`; also attaches Pezzo `465-II` to `465`, Pezzo `467-1` to `467`, Cornice `1 (Fackelmann)` to `466` | Mostly redundant with B2 metadata, plus extra Pezzo wiring |
| `d5b9ebc4-31a9-5368-90ac-eeb2893998db` | Creates Cornice `1 (Fackelmann)` under PHercs `228`, `444`, `1063` | Hard-coded list says `1063` but metadata.csv has the UUID under PHerc `1073` (B2). **Likely typo — confirm `1063` vs `1073`.** Result is a phantom Cornice under PHerc `1063`. |
| `6c88ad2a-7a6a-5055-b832-babd9f859f37` | Creates Cornice `1 (Fackelmann)` under PHercs `244`, `456`, `461`, `1603` | Redundant with B2 metadata. Could potentially be removed. |
| `4ca2ccaa-181d-5046-bb65-b18280595e79` | Pezzo `Scorza` under PHerc `465` | |
| `67105cd9-9755-5bd0-9194-2444874fd54a` | Pezzo `Scorza` under PHerc `467` | |
| `e94d8207-3802-57e9-a5bd-b8030a1935b9` | Pezzo `Scorza` under PHerc `467` | |

**Question for papyrologists:** Now that the UUID-phase fix (`set_alias_on_assigned_node`) handles multi-PHerc cornice cases more cleanly, are these hard-codings still needed? Especially `02160e53`, `d5b9ebc4`, `6c88ad2a` which largely overlap with the B2 data.

---

## Section 3 — Naming inconsistencies between the UUID sheet and metadata

The UUID sheet (`uuid_file_*.csv`) often uses short labels like `1 (Oslo)` while metadata uses the full name `1 (Osloense)`. The loader now records the UUID-sheet form as `name` on the existing node (the `displayName` is set from the metadata form). Examples below — these all resolve correctly today; listed here only as a record of the duality.

- `(Oslo)` ↔ `(Osloense)` — pervasive; affects most B1/B2 entries above
- `Cass.78 s.n. C/D/E/F` (UUID sheet) ↔ `Cass. 78 s.n. C/D/E/F` (metadata)
- `cd2d27bf`: UUID sheet `1083 = s.n. A cass. 92` ↔ metadata PHerc `1083`

---

## Section 4 — UUID-sheet rows whose PHerc isn't recorded as such in metadata

Cases where the UUID sheet's PHerc value doesn't directly match a metadata `PapyrusNum`:

- `caa97a09-ba6d-5ea1-ae3d-ad4a08d9a31e` — UUID sheet PHerc `1362`, Cornice `Cass.75`; metadata PHerc `1362` row has no Cornice. Loader creates Cornice `Cass.75` under PHerc `1362` from the UUID sheet. Confirm Cornice belongs to PHerc 1362.
- `614efdb7-4095-56f1-b234-35b4a3bcac1a` — Same pattern, PHerc `1363` + Cornice `Cass.75`.
- `a7bee49b-cca5-53dc-b7cd-82c44c49ca2a` — UUID sheet PHerc `72 frammento`, Cornice `Cass.7`. Metadata PHerc `72` exists but UUID sheet uses the longer label `72 frammento` as the alternate name. Confirm intended.

---

## Section 5 — 2026 scan-CSV reload (PGS / Spectral)

The 2026 scan datasets (`input_data/pgs_datasets_20260601(in).csv`,
`input_data/spectral_datasets_20260601 1(in).csv`) were reconciled against the 2023 CSVs
(`photogrammetry-scans-20231107.csv`, `spectral-scans-20231108.csv`) and reloaded. The 2026
spectral file shipped with many blank `sample uuid` values and dropped the `sample uuid 2`
column. The reconciliation (`preprocessing/reconcile_spectral_2026.py`) wrote the ground-truth file
`input_data/spectral_datasets_20260601_reconciled.csv`. Items below were passed through faithfully
and warrant confirmation.

- **78 spectral `sample uuid` values backfilled from 2023** — present in the 2023 CSV for the same
  scan `uuid` but blank in the 2026 file. Restored. Confirm the 2023 associations are still correct.
- **19 spectral scans have no `sample uuid` in either 2023 or 2026** — genuinely unknown; loaded as
  unlinked SpectralRaw nodes (no `BELONGS_TO`).
- **147 brand-new 2026 spectral scans have no `sample uuid`** — loaded as unlinked nodes. Breakdown:
  95 `FocusCheck*`, 17 `*test/TEST*`, 5 `exp/Exposures`, and 30 "other" that are almost all
  `SETUP*` / `COLOR*` / `FLATS*` / `ColorCheck*` calibration captures. **Only two look like real
  artifacts and should be checked**: `MVDaily_20220930/PHerc1670Cn01` and
  `MVDaily_20230209/PHerc1506Cr28` — confirm whether these should be linked to an EduceLabID.
  (The full breakdown is reproducible by re-running `preprocessing/reconcile_spectral_2026.py`.)
- **1 dropped secondary `sample uuid 2` link** — 2023 spectral scan `ce015560-122b-46dc-a5cd-915191a3261d`
  had a second sample `c5ca1b3a-5853-54cf-9ced-43b86fccd0b0` in addition to its primary
  `10517d86-92b4-52de-b9e3-caae671ebec0`. The 2026 schema removed `sample uuid 2`, so only the primary
  `BELONGS_TO` link was recreated. **Confirm whether the secondary association should be preserved**
  (and, if so, how, since the source column is gone).

## Section 6 — Name model migration (canonical displayName + aliases) and sample-UUID cross-check

The PHerc/Cornice/Pezzo name model was changed to a single canonical `displayName` (always
populated) plus an `aliases` match-surface (see `.claude/plans/name_displayname_alias_model.md`
and CLAUDE.md). The live DB was migrated once via `preprocessing/migrate_name_aliases.py` (`--apply`,
then `--merge-dupes`); a pre-migration backup of all node names was captured (since discarded
after the migration was verified).

**Migration outcomes:**
- **203 null-`displayName` nodes backfilled** (`displayName = coalesce(displayName, name)`): 30 PHerc
  + 173 Cornice. Most are Casetta cornici (legitimate `Cass. N` names) now carrying `Cass.N` /
  `Casetta N` / `Casetto N` synonyms; a handful are genuinely informal names (`tavoletta`, `frammenti`,
  `folded sheet`, `TH A 74`, …) that **may want a curated canonical name from the metadata sheet**.
- **8 duplicate PHerc groups merged** (16 → 8 nodes): seven were a real metadata-rich `PHerc NNN`
  (532, 571, 601, 691, 695, 957, 1512) paired with a phantom null-`displayName` twin holding one
  orphaned Cornice — the old uuid-sheet fallback created these; the cornice was reattached. The
  eighth was the `tavoletta` / `tavoletta ` (trailing space) whitespace pair. Metadata properties on
  the surviving node were preserved.

**Sample-UUID vs path cross-check (now the committed `cli/sample_uuid_check.py` / `el-hercdb-sample-uuid-check`).**
Each scan path encodes the artifact it depicts; the `sample uuid` should resolve to that artifact.
Genuine issues still needing a human decision:
- **10 wrong sample UUIDs (`PHERC_MISMATCH`)** — the path names one scroll but the UUID resolves to a
  different PHerc (e.g. path `PHerc1413` → UUID's artifact is `PHerc 1014`; also 45↔50, 1436↔1431,
  509↔506, 121↔99, 208↔207, 360↔1232, 1515↔1508, 1045↔118a). Likely fat-finger / adjacent-row entry
  errors in the scan CSVs. **Correct in source.**
- **3 wrong subdivision (`SUBDIV_MISMATCH`)** — right PHerc, wrong cornice (786 Cr3→Cornice1,
  899 Cr2→Cornice1, 207 Cr9→Cornice5). **Correct in source.**
- **16 sample UUIDs present in `uuid_file_20260427.csv` but linked to no artifact (`UUID_NOT_IN_DB`,
  45 scan rows)** — 13 have **blank `PHerc`/`Pezzo` columns** in the uuid file so no `ASSIGNED_TO`
  edge was ever made (scans of PHerc 339 Cr1–6, 1413 Cr1–4, 197 Cr2, 1416 Cr5, + 1 genuine 2025 test
  scan). **Fill in the PHerc/Pezzo for those uuid-file rows and re-run `metadata_loader.py`.** The
  other 3 (`bda57bd5`→PHerc 494, `02154ec8`→PHerc 21 Pz1, `9ba9ad06`→PHerc 1784) were *replaced*; their
  successor UUID is correctly assigned, so they resolve via the `REPLACES` chain — no action.
- **2 `CASETTA_MISMATCH`** — both benign path-string truncations pointing at the right artifact
  (`Cassetto 2 s.n.` missing the trailing ` A`; `Cass.38 (remove` truncated from
  `Cass. 38 (removed fragments)`). No action unless the path strings should be corrected.
- **36 `NONNUMERIC_PHERC`** — paths with no checkable artifact id (`PHercNULL`, `PHerctest`,
  `PHerc_Pezzo01`, etc.); calibration/test, not artifact scans.

## Section 7 — CSV-sourced scan-completeness report + curated review (pre-load)

To answer "which physical objects still need a PGS/Spectral scan, and which museum holds them"
ahead of a scanning trip — **without** loading the new scans into Neo4j — `el-hercdb-scan-report
--scans-from-csv` reads coverage directly from the scan CSVs (PGS = `pgs_datasets_20260601(in).csv`,
Spectral = the reconciled `spectral_datasets_20260601_reconciled.csv`, which recovers 78 sample
uuids vs the raw `(in)` file) and joins against the already-loaded artifact hierarchy + institution.
Read-only on the DB. Produces `scan_completeness_full.csv`, `_issues.csv`, and a curated
`scan_completeness_review.csv`.

**Review counts (run 2026-06-04, live DB):** 4,811 full rows; 1,385 issues rows; 58 review rows —
13 `WRONG_SAMPLE_UUID` (10 PHerc + 3 subdivision; same as Section 6, **correct in source**) and
45 `ORPHAN_SAMPLE_UUID` (the Section-6 `UUID_NOT_IN_DB` scans; fill in the 13 blank-`PHerc` uuid-file
rows + re-run `metadata_loader.py`). The review report flags **sample-uuid data errors only**.

It **deliberately excludes** two things that aren't sample-uuid errors:
- `INCOMPLETE_FILES` — 13 (artifact, modality) pairs scanned but with no fully-complete scan (e.g.
  PHerc 182's PGS scans have zero-byte files; 1476/1827 Spectral have missing files). Each is missing
  a good scan in **one** modality (none in both). These already appear in the **issues CSV** with an
  `incomplete` status, so they're not duplicated here. (Separately, 39 more (artifact, modality) pairs
  have a bad scan *plus* a good one — not flagged anywhere, since a usable scan exists.)
- `UNLINKED_UUID` — 130 rows in `uuid_file_20260427.csv` carry an EduceLab ID + UUID but blank
  `PHerc`/`Pezzo/Cr`, so `metadata_loader.py` creates the `EduceLabID` node with no `ASSIGNED_TO`
  edge. Minted/reserved UUIDs with no physical object — data hygiene, not "needs scanning"
  (`db.find_unassigned_educelabids()` lists them if needed).

**Known limitation:** the cross-check matches PHerc number **sets**, so it cannot catch an
`118a`↔`118b` swap (scan paths omit the alpha suffix). The coverage report itself is unaffected —
it attributes every scan by `sample uuid` to the exact Neo4j node, so `118a` and `118b` are always
distinct rows.

## Section 8 — Non-numeric `PHerc Number` values in the metadata CSV

A catalog of every non-numeric value in the `PHerc Number` column of
`metadata_file_20260427.csv` — 39 unique values (vs. 23 in the October 2025 file). The
loaders pass these through faithfully; they are catalogued here for papyrologist review.
Each entry lists the PHerc Number and the Cornice column values that follow it before the
next PHerc row.

### Casettas

Storage cases, not scrolls. Cornice column contains the group casetta label rather than a number.

| PHerc Number | Cornice rows |
|---|---|
| `Cass. 78 s.n. C` | `Cass.78 s.n. da A a F` |
| `Cass. 78 s.n. D` | `Cass.78 s.n. da A a F` |
| `Cass. 78 s.n. E` | `Cass.78 s.n. da A a F` |
| `Cass. 78 s.n. F` | `Cass.78 s.n. da A a F` |

### Foreign / Non-PHerc collections

| PHerc Number | Cornice rows | Notes |
|---|---|---|
| `Haun.1` | *(none)* | Copenhagen (Denmark) |
| `Paris.1` | *(none)* | Paris (Bibliothèque de l'Institut de France) |
| `Paris.2` | *(none)* | Paris |
| `Joannowsky Papyrus` | `I` `II` `III` `IV` `V` `VI` `VII` `VIII` | Naples; Roman numeral Cornici |

### Sine-numero Oslo fragments (`PHerc. s.n.`)

All cornice values carry the `(Osloense)` label. Unnumbered fragments held in Oslo.

| PHerc Number | Cornice rows |
|---|---|
| `4 PHerc. s.n.` | `1 (Osloense)` |
| `PHerc. s.n. A Cass II` | `1 (Osloense)` `2 (Osloense)` `3 (Osloense)` `4 (Osloense)` |
| `PHerc. s.n. B+C+D Cass I` | `1 (Osloense)` |
| `PHerc. s.n. C Cass II- s.n. A Cass XXXII` | `1 (Osloense)` |
| `PHerc. s.n. Cass LI` | `1 (Osloense)` `2 (Osloense)` |
| `PHerc. s.n. Cass XLII` | `1 (Osloense)` |
| `PHerc. s.n. Cass. LVIII` | `1 (Osloense)` |
| `PHerc. s.n. I-III Cass CXIV` | `1 (Osloense)` |
| `PHerc. s.n. IV Cass XCIV` | `1 (Osloense)` |
| `PHerc. s.n. 1-3 Cass CVI - s.n. Cass CXII` | `1 (Osloense)` |
| `PHerc. s.n.A+B Cass I` | `1 (Osloense)` |

### Likely PHerc — non-standard identifiers

**Slash-combined IDs** (two historical catalog numbers for the same physical scroll):

| PHerc Number | Cornice rows |
|---|---|
| `152/157` | `1`–`23` |
| `336/1150` | `1`–`9` |
| `908/1390` | `1`–`5` |
| `1007/1673` | `1`–`17` |
| `1078/1080` | `1` |
| `1479/1417` | `1`–`12` |
| `1577/1579` | `Scorze 1572-1579` |

**"bis" suffix:**

| PHerc Number | Cornice rows | Notes |
|---|---|---|
| `927bis` | `1` `2` | Two standard Cornici |
| `0927 bis` | *(none)* | Likely a duplicate/alternate record for `927bis`; no cornice rows |
| `1083bis` | `Scorze 1820-1821-1083bis-Cass.92 s.n. A` | Casetta-style label instead of a number |

**Letter-suffix PHerc:**

| PHerc Number | Cornice rows | Notes |
|---|---|---|
| `118a` | *(none in Cornice col)* | 12 Pezzo sub-rows (col 3) instead — different structure, Oxford |
| `118b` | *(none)* | Only top-level row |
| `0101b` | *(none)* | Two rows but no Cornice entry |
| `0137a` | *(none)* | Only top-level row |
| `0137b` | *(none)* | Only top-level row |

### Data-entry errors (cell overflow)

Not real PHerc entries — note or citation text from column 0 overflowed into the PHerc Number
column (col 1), creating spurious non-numeric values.

| PHerc Number (col 1 content) | Reconstructed context | Cornice rows |
|---|---|---|
| `in realtà` | *"4 degli 8 disegni napoletani a in realtà al PHerc. 1818."* — note near PHerc 1113 | `al PHerc. 1818."` `Scorze da 1112 a 1114` |
| `R. è ipotizzata sulla base dell'esame degli stessi disegni e dei documenti."` | *"La data di redazione dei disegni R. è ipotizzata…"* — note near PHerc 1177 | *(none)* |
| `Relazione sui Papiri Ercolanesi letta alla R. Accademia dei Lincei` | Comparetti bibliography citation split across cells, near PHerc 1119 | `in D. Comparetti-G. De Petra` |
| `PHerc. 1116` | Same Comparetti citation continuing on next row; col 2 contains `PHerc. 1117` | `PHerc. 1117` `Scorze 1115-1572` |
| `PHerc 199-Cornice 2-02990-1000nmS40{OGU}.jpg` | Note about PHerc 199 with a filename in col 1; cornice rows beneath likely belong to PHerc 199 | `1` `2` `3` `1`–`7 (Osloense)` |

### Change vs. the October 2025 file

- **New group:** 11 `PHerc. s.n.` Oslo sine-numero fragments (not in old file).
- **New group:** 5 data-entry cell-overflow errors (not in old file).
- **Count change:** `1007/1673` now has 17 cornice rows (old file showed 6).
- **Retained:** all 23 non-numeric entries from the old file are still present.

## Maintenance

Add a new entry whenever a CSV anomaly is found that the loaders pass through faithfully but that a domain expert should verify. When a question is resolved, replace the “Question” line with the resolution and date so the file remains a record of decisions.
