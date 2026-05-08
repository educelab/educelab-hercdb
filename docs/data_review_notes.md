# Data review notes

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

## Maintenance

Add a new entry whenever a CSV anomaly is found that the loaders pass through faithfully but that a domain expert should verify. When a question is resolved, replace the “Question” line with the resolution and date so the file remains a record of decisions.
