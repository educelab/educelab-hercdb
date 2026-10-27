# Deploy and migration log

A dated record of what was run against which database, and of server deploys. Newest
entry first. Hosts: **.41** = production (`bolt://10.33.46.41:7687`, also runs the REST
server), **.43** = dev and backup target (Neo4j only). .43 is overwritten every night by
a snapshot of .41, so a run on .43 is a rehearsal and does not last.

---

## 2026-10-27 — 23 Process statuses lost on 2026-10-23 recorded (.41)

The jobs of 23 pipelines submitted on 2026-10-23 ended on ECC between 16:41 and 21:09 UTC,
while Neo4j refused writes. Their reports never landed, so .41 still showed them
`submitted` (one `archiving`) with nothing in squeue. `sacct` showed:

- **20 finished:** every job, including the checksum-verified `-archive` job, ended
  `COMPLETED`. That's 16 PGS, 3 REG (`347e759f`, `af197ef3`, `f2991bcd`) and 1 WEB
  (`362063a2`). Set to `completed`, with the archive job's end time.
- **3 failed:** WEB `ce4324cf`, `a9c1aa15` and `64fb3856`, whose `webify` exited 1 with
  no archive job. Set to `failed` with the webify end time, and the note `webify exited 1;
  report lost in the 2026-10-23 outage; recorded 2026-10-27 from sacct`. These are real
  failures (PHerc 1180, Cornici 01, 03 and 04). They wait at the retry cap until the cause
  is found, then `web_autoqueue.py --retry <path>`.

Written through the REST API from ECC by a one-off script. It read each Process's current
status first and changed only open ones (`submitted`/`running`/`archiving`), then read
each back. The WEB work-list went from 4 to 3 rows.

Dev (.43) didn't help here: its newest Process is from 2026-10-20, so it hadn't taken
a snapshot of .41 since then (Neo4j on .43 was also down after a reboot today).

## 2026-10-27 — 0.3.12 on .43 and .41

`hercdb_deploy 0.3.12` on both, the same day the tag published to PyPI. `/openapi.json`
reports `0.3.12` on .43 and .41. The release adds the server-side REG/WEB work-list
(`GET /datasets/{REG|WEB}/unprocessed`, #66). It's an addition only, with no data change.
On the dev graph its REG rows matched acquisition-workflow's `worklist.candidates()`, in
3 queries in place of 6,257 requests. Rollback: `hercdb_deploy 0.3.11`.

The ECC autoqueue is still off. It goes back on after acquisition-workflow calls this
endpoint in place of `candidates()`, and after the Friday (2026-10-23) records are cleaned up.

## 2026-10-27 — 0.3.11 on .41

`hercdb_deploy 0.3.11`, the same day the tag published to PyPI. `/openapi.json` on .41
reports `0.3.11`. The release ships one log line per request and a 503 for a panicked or
starting Neo4j (#65), plus the changes since 0.3.10 (#23, #40, #43, #45, #47, #59, #61).
The data fixes among those had already been run on .41 (entries below). Rollback:
`hercdb_deploy 0.3.10`.

The ECC autoqueue is still off; it waits on #66.

## 2026-10-26 — .41 log retention capped, after the 2026-10-23 disk-full outage

**What happened.** On 2026-10-23 the .41 root disk (48 GB) filled to 100%, almost all of it
`/var/log/syslog` and `syslog.1` (41 GB). Neo4j hit the full disk at about 16:40 UTC and
refused all transactions (`TransactionStartFailed`) until it was restarted. Nearly every
syslog line came from uvicorn (`hercdb.service`). Each API request writes three lines (the
uvicorn access log, the request middleware and the handler's own line), and syslog rotated
weekly with no size limit. The log rate rose about tenfold around 2026-10-11, which fits the
acquisition-workflow `dispatch_all.sh` tick (added 2026-10-08, every 10 minutes): its REG/WEB
work-lists are built on the client, with several requests per artifact. The Oct 11–23 logs
were deleted to free space, so the per-endpoint mix can't be confirmed. The campus power and
network outage on the morning of 2026-10-23 came after the rise and did not cause it.

**Recovery (2026-10-23).** Deleted `syslog.1` and emptied `syslog` in place. Stopped the ECC
autoqueue (scrontab). Restarted Neo4j: recovery replayed 20 transactions and rolled back 0;
51,175 nodes. Restarted `hercdb.service`. With the autoqueue off, syslog grows about 70 MB/day.

**Writes may have been lost.** From about 16:40 UTC until the restart, a write that reached
the panicked database got the error swallowed by `_run_query` (#34), not a 503, so clients
did not retry. Pipeline status updates from that window still need checking against what
was archived.

**Changes on .41 (2026-10-26)**, so logs keep at most two weeks:

- `/etc/logrotate.d/rsyslog`: `weekly` → `daily`, `rotate 4` → `rotate 14`, added
  `maxsize 500M`. Backup at `~/rsyslog.logrotate.bak`.
- `/etc/systemd/system/logrotate.timer.d/hourly.conf`: logrotate runs hourly, so
  `maxsize` is enforced within an hour.
- `/etc/systemd/journald.conf.d/retention.conf`: `SystemMaxUse=500M`,
  `MaxRetentionSec=2week` (journal went from 768 MB to 400 MB).

Still open: a disk-usage alert, cutting the API's log lines to one per request, a 503 for
a panicked database, and a server-side REG/WEB work-list so a tick makes one request, not
thousands. The ECC autoqueue stays off until that last one is done.

## 2026-10-22 — #45: two-number papyri's numbers added as aliases

`preprocessing/migrate_two_number_aliases.py --apply`. It adds both numbers of each
two-number papyrus to its `aliases`; `displayName` is unchanged. It was run read-only first,
then with `--apply`, then read-only again (0 left).

- **.43:** 7 papyri (`1007/1673`, `1078/1080`, `1479/1417`, `152/157`, `1577/1579`,
  `336/1150`, `908/1390`). "1673" and "1007" now resolve to `1007/1673` at score 100.

## 2026-10-22 — #43: 76 Cr 05 LR scan linked to Right (.43 and .41)

`python -m educelab.hercdb.loader.extra_scan_links --apply`. It adds the `BELONGS_TO` links
listed in `input_data/extra_scan_links.csv`. It was run as a check first, then with
`--apply`, then as a check again (`linked`).

- **.43:** linked spectral scan `ce015560` to 76 Cr 05 Right (`c5ca1b3a`). It is now
  listed under both Left and Right. The SPEC work-list is unchanged, because each tray's
  newest spectral scan is its own.
- **.41:** the same link, with the same result. Run from the workstation with the
  `~/.educedb.prod` credentials; the module printed the target URI first.

## 2026-10-22 — #61: shared trays' uuid-sheet names moved onto the EduceLabID (.43 and .41)

`preprocessing/fix_shared_tray_names.py --apply`. On every EduceLabID assigned to more than
one node, it moves the uuid-sheet row's names onto the EduceLabID (`sheet_pherc`,
`sheet_cornice`) and removes them from nodes they don't name. It was run read-only first,
then with `--apply`, then read-only again (0 left).

- **.43:** 48 nodes cleaned (47 PHercs, e.g. `924-935` off 924 and 935, plus `2 (oslo)` off
  1191's `1 (Osloense)`); names recorded on 22 trays.
- **.41:** the same 48 nodes and 22 trays, with the same result. Run from the workstation
  with the `~/.educedb.prod` credentials; the script printed the target URI first.

## 2026-10-22 — APOC on .43

The loader's alias writes use `apoc.coll.toSet`. .41 had APOC and .43 didn't, so those
writes silently did nothing on .43 (the error is swallowed, #34).

- **.43:** copied the bundled `labs/apoc-5.26.31-core.jar` into `plugins/`, set
  `dbms.security.procedures.unrestricted=apoc.*` (as on .41), and restarted Neo4j.
  `RETURN apoc.version()` gives 5.26.31. `plugins/` isn't touched by the nightly restore.
- **.41:** unchanged (APOC 5.26.27 on Neo4j 5.26.30).

## 2026-10-22 — #59: phantom 1063 cornice removed on .43 and .41

`preprocessing/fix_1063_phantom_cornice.py --apply`. It deletes `Cornice 1 (Fackelmann)` under
PHerc 1063, but only while nothing else is attached to it. It was run read-only first, then
with `--apply`, then read-only again (0 left).

- **.43:** 1 node deleted. Tray `d5b9ebc4` now reads "Cornice 1 (Fackelmann): PHerc. 228,
  444, 1073", and 1063 has no cornici.
- **.41:** the same node deleted, with the same result. Run from the workstation with the
  `~/.educedb.prod` credentials; the script printed the target URI first.

## 2026-10-22 — #40: papyrus-level UUIDs removed on .43 and .41

`preprocessing/fix_pherc_level_uuids.py --apply`. It removes a PHerc's `ASSIGNED_TO` when
one of that PHerc's own objects carries the same UUID. It was run read-only first, then with
`--apply`, then read-only again (0 left).

- **.43:** removed 3 edges: 72 (`a7bee49b`, also on `Cass.7`), 1362 (`caa97a09`) and 1363
  (`614efdb7`, both also on `Cass.75`). `/all-datasets` no longer lists their datasets
  twice (72: 12 → 6 rows; 1362 and 1363: 6 → 3).
- **.41:** the same 3 edges removed, with the same result. Run from the workstation with
  the `~/.educedb.prod` credentials; the target URI was checked first.

## 2026-10-21 — REST server moved to a PyPI venv; 0.3.10 on .43 and .41 (#52)

The server now runs one exact PyPI release from `~/hercdb-server`, not a git checkout.
Deploys go through `hercdb_deploy X.Y.Z` (`scripts/deploy_server.sh`, installed in
`/usr/local/sbin`). See `SERVER_SETUP.md`, "Deploying a release".

- **.43 (new dev REST server):**
  - The first REST server on .43. It reads .43's own Neo4j, which holds last night's prod snapshot.
  - Installed with `hercdb_deploy` as 0.3.9, then upgraded to 0.3.10. The rollback line was printed.
  - It has its own token (user `mami-dev`), which .41 refuses with 401.
  - Checked: `/check-token` valid, `GET /pherc` 1,873 rows, `/subdivisions?pherc=1007/1673` 17 cornici.
  - Left running. It answers 503 while the nightly snapshot is being restored.
- **.41 (production):**
  - The clone of `develop` was already serving 0.3.10.
  - The switch to the venv followed "Switching a server that runs from a git checkout": unit backed up to
    `~/hercdb.service.clone-backup`, `ExecStart`/`WorkingDirectory` pointed at the venv, restarted.
  - Checked: `/openapi.json` reports 0.3.10, a request with no token and one with the .43 token both get 401,
    and the pipeline UI works.
  - The clone is kept for now and will be removed later.

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
