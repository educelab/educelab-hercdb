# Deploy and migration log

A dated record of what was run against which database, and of server deploys. Newest
entry first. Hosts: **.41** = production (`bolt://10.33.46.41:7687`, also runs the REST
server), **.43** = dev and backup target (Neo4j only). .43 is overwritten every night by
a snapshot of .41, so a run on .43 is a rehearsal and does not last.

---

## 2026-10-21 — 0.3.9 migrations on .43 and .41

Both were run from a workstation, with the target URI checked before each write. Each was
run read-only first, then with `--apply`, then read-only again to confirm. Writes from the
cluster carried on during the runs. Neither migration overwrites a value that is already set.

### `preprocessing/migrate_release_flag.py --apply`

Sets `released = true` on every releasable dataset with no flag yet.

| Host | Datasets without a flag | After |
|---|---|---|
| .43 | 14,928 | 0 |
| .41 | 14,926 | 0 |

On .41: PGSRaw 3,738, SpectralRaw 3,837, PGSProcessed 1,483, SpectralProcessed 3,508,
Registered 1,286, WebProcessed 1,074. Datasets written by 0.3.9 pipelines already had a
flag and were left alone.

### `preprocessing/migrate_dataset_uuids.py --data-root <copy> --apply`

Sets a processed dataset's `uuid` from its `metadata.json`. Run without `--mint-missing`.

| | PGSProcessed | SpectralProcessed | Registered | WebProcessed | Total |
|---|---|---|---|---|---|
| No `uuid` before | 1,483 | 3,508 | 1,286 | 1,074 | 7,351 |
| Set from `metadata.json` | 1,289 | 3,505 | 1,119 | 1,005 | 6,918 |
| Left without one | 194 | 3 | 167 | 69 | 433 |

- The counts were identical on .43 and .41.
- Afterwards no `uuid` was shared by two datasets, and the `uuid` index was ONLINE on all
  six dataset labels.
- All 433 left over are outputs whose newest Process `failed`, so nothing was archived
  for them. They were deliberately not minted. See `data_review_notes.md` §10.

**Where the files came from.** The cluster copies of processed data are deleted as the
pipelines go, so the `metadata.json` files were taken from the Globus `herc-archive`
endpoint:
1. A read-only query on .41 exported the `path` of every processed dataset without a
   `uuid`.
2. On ECC, in the acquisition-workflow venv, a one-off script ran one Globus transfer of
   `<archive basedir>/<path>/metadata.json` for those paths only. It wrote them flat, as
   `NNNNN.json` in list order, into a scratch directory outside the pipeline data tree.
   Missing source files were skipped.
3. The directory was rsynced to the workstation and rebuilt as `<path>/metadata.json`,
   and that tree was passed as `--data-root`.

The one-off scripts were not committed.
