# hercdb Neo4j Schema – Node Properties

Derived from `src/educelab/hercdb/loader/graph_loader.py`.

| Node Type | Property | Data Type | Example |
|---|---|---|---|
| **PHerc** | `displayName` | string | `"421"` |
| | `name` | string *(deprecated)* | `"PHerc 421"` |
| **Cornice** | `displayName` | string | `"A"` |
| | `name` | string *(deprecated)* | `"Cornice A"` |
| **Pezzo** | `displayName` | string | `"2a"` |
| | `name` | string *(deprecated)* | `"Pezzo 2a"` |
| **Disegni** | `name` | string | `"Disegni di Napoli"` |
| **EduceLabID** | `uuid` | string | `"550e8400-e29b-41d4-a716-446655440000"` |
| | `educelab_id` | string | `"EL-1234"` |
| **Author** | `name` | string | `"Philodemus"` |
| **Language** | `name` | string | `"Greek"` |
| | `url` | string *(optional)* | `"https://..."` |
| **Unroller** | `name` | string | `"Piaggio"` |
| **UnrollingMethod** | `name` | string | `"Piaggio method"` |
| **OsloMethod** | *(none)* | — | — |
| **CavalloScribalStyle** | `name` | string | `"rustic capital"` |
| **ObjectFormat** | `format` | string | `"scroll"` |
| | `url` | string *(optional)* | `"https://..."` |
| **MaterialType** | `format` | string | `"papyrus"` |
| | `url` | string *(optional)* | `"https://..."` |
| **CustodialInstitution** | `name` | string | `"Biblioteca Nazionale di Napoli"` |
| | `url` | string *(optional)* | `"https://..."` |
| **CustodialLocation** | `name` | string | `"Naples"` |
| | `url` | string *(optional)* | `"https://..."` |
| **FlatbedScanDataset** | `imgNum` | string | `"001"` |
| | `negSeries` | string | `"BN"` |
| | `negStorage` | string | `"cabinet-3"` |
| | `pherc` | string | `"421"` |
| | `cornice` | string | `"A"` |
| **PGSRaw** | `uuid` | string | `"550e8400-..."` |
| | `path` | string | `"/data/pgs/421/..."` |
| | `date_start` | string (ISO datetime) | `"2024-01-15T09:00:00"` |
| | `date_end` | string (ISO datetime) *(optional)* | `"2024-01-15T11:00:00"` |
| | `complete` | boolean *(optional)* | `True` |
| **SpectralRaw** | `uuid` | string | `"550e8400-..."` |
| | `path` | string | `"/data/spectral/421/..."` |
| | `date_start` | string (ISO datetime) | `"2024-01-15T09:00:00"` |
| | `date_end` | string (ISO datetime) *(optional)* | `"2024-01-15T11:00:00"` |
| | `complete` | boolean *(optional)* | `True` |
| **PGSProcessed** | `path` | string | `"/data/pgs_proc/421/..."` |
| **SpectralProcessed** | `path` | string | `"/data/spec_proc/421/..."` |
| **Registered** | `path` | string | `"/data/registered/421/..."` |
| **WebProcessed** | `path` | string | `"/data/web/421/..."` |
| **Process** | `stage` | string | `"PGS"`, `"SPEC"`, `"REG"`, `"WEB"` |
| | `start_time` | string (ISO datetime) | `"2024-01-15T09:00:00"` |
| | `slurm_id` | string/int | `"12345"` |
| | `status` | string | `"submitted"`, `"completed"`, `"failed"` |
| | `end_time` | string (ISO datetime) *(optional)* | `"2024-01-15T11:00:00"` |
| **Pipeline** | `pipeline_id` | string | `"pipeline-2024-001"` |

## Notes

- `displayName` is the primary lookup key for physical nodes (PHerc, Cornice, Pezzo); the older `name` property is deprecated.
- `ObjectFormat` and `MaterialType` use `format` as their key property (not `name`), unlike all other metadata nodes.
- `OsloMethod` has no properties — it is used as a singleton/tag node.
- `Process.stage` stores the process type in Neo4j (`"PGS"`, `"SPEC"`, `"REG"`, `"WEB"`), but the Python API and REST layer refer to this field as `proc_type`.
- All relationships in the current loader carry no properties.
