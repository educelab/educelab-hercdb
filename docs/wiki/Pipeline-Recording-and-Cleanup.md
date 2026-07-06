# Pipeline Recording & Cleanup

When the acquisition-workflow `submit_uber_pipeline.py` submits a processing
pipeline, it records that pipeline and its stages in HercDB so the database
reflects what is running on the cluster.

## What gets recorded

For each selected tray, on submission the script writes:

- one **Pipeline** node, keyed by the run's `uber_job_id` (e.g.
  `uber-1a2b3c4d`), linked to the artifact's **EduceLabID** (`FOR` relationship);
- one **Process** node per enabled stage — `PGS`, `SPEC`, `REG`, `WEB` — each
  with its `slurm_id`, `start_time`, and `status` (`submitted`), linked to its
  input and output dataset nodes.

Stages are recorded in **dependency order**, because each downstream stage
matches the output nodes the upstream stages create:

| Stage | Inputs | Output node |
|---|---|---|
| `PGS` | the raw `PGSRaw` dataset | `PGSProcessed` |
| `SPEC` | the raw `SpectralRaw` dataset | `SpectralProcessed` |
| `REG` | the `PGSProcessed` + `SpectralProcessed` outputs | `Registered` |
| `WEB` | the `Registered` output | `WebProcessed` |

The graph shape: `Pipeline -[:FOR]-> EduceLabID`, `Process -[:STAGE_OF]->
Pipeline`, and `input -[:INPUT]-> Process -[:OUTPUT]-> output`.

## When recording happens

Recording runs on **both** dry-run and real submissions:

- **Real run** — processes carry the actual SLURM job ids.
- **`--dry-run`** — no SLURM jobs are submitted, but the records are still
  written, with placeholder slurm ids (`######`). This lets the write path be
  verified end-to-end before any real submission.
- **`--no-record-pipeline`** — turns recording off entirely.

Each recorded tray prints `Recorded pipeline <uber_job_id> (N process(es)).` —
note the id for verification or cleanup.

Recording is **best-effort**: a failure to write one process warns and
continues; it never blocks the submission.

## Status lifecycle (submitted → completed / failed)

Recording at submission marks every Process `submitted`. Each stage then updates
its own Process when it finishes, from the compute node:

- The four stage scripts (`pipeline_recon.py` → PGS, `pipeline_spectral.py` →
  SPEC, `pipeline_registration.py` → REG, `pipeline_webify.py` → WEB) wrap their
  `main()` in `report_stage(<PROC_TYPE>)` (`hercdb_status.py`). On a clean exit it
  sets the Process `completed`; on an exception or a nonzero `sys.exit` it sets
  `failed`. The original exit status is preserved, so SLURM's `afterok`
  dependencies are unaffected.
- **Auth:** the stage scripts report over the REST client using `HERCDB_HOST` /
  `HERCDB_TOKEN` (plus optional `HERCDB_PORT` / `HERCDB_SCHEME`). With the default
  `client` backend `submit_uber_pipeline.py` already requires these credentials,
  so a run with none configured **exits immediately** (pointing you at
  `source ~/.hercdb_client.env`) instead of launching jobs that can't report.
  However you supply them — by sourcing that file or via `--host`/`--token` — the
  submit script copies the resolved values into each job's environment via
  `sbatch --export=ALL`. (On the stage-script side the report is still a safe
  no-op if `UBER_JOB_ID`/`HERCDB_*` happen to be absent, so it never fails the
  stage's actual processing work.)
- **Hard-kill gap (by design):** a job killed by OOM, time limit, `scancel`, or a
  node crash terminates without running any Python, so its Process stays
  `submitted`. A Process stuck at `submitted` long after the job should have
  finished is the signal to investigate and fix the status manually (e.g.
  `PUT /pipelines/{id}/processes/{proc_type}/status` with `{"status":"failed",...}`,
  or `HercClient.update_process_status(...)`).

### UUID replacement chains are handled

A scan taken before a UUID was replaced still `BELONGS_TO` the **predecessor**
UUID, not the artifact's active one. `PGS`/`SPEC` recording matches the raw input
across the pipeline EduceLabID's REPLACES chain (`[:REPLACES*0..]`), mirroring the
read path — so selecting such a scan records correctly. (`REG`/`WEB` match the
upstream output nodes this pipeline produced, so they are never affected.)

## Verifying records

Over REST (from anywhere with a token):

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://<vm-host>:8000/pipelines/<uber_job_id>/confirmation"
```

Or on the VM with the admin tool:

```bash
uv run el-hercdb-pipeline-cleanup --list   # every pipeline + its artifact UUID
```

## Cleaning up (DB-admin tool)

`el-hercdb-pipeline-cleanup` is a HercDB admin CLI (it talks **straight to
Neo4j**, no REST server needed — the admin runs it on the database host). It is
the companion to recording: use it to remove test pipelines created during
dry-run testing.

```bash
# list what exists
uv run el-hercdb-pipeline-cleanup --list

# delete one or more by id (the uber_job_id from the submit output)
uv run el-hercdb-pipeline-cleanup uber-1a2b3c4d uber-5e6f7a8b

# -y skips the confirmation prompt
uv run el-hercdb-pipeline-cleanup uber-1a2b3c4d -y
```

Deleting a pipeline removes:

- the **Pipeline** node,
- all its **Process** nodes,
- the **output** dataset nodes they produced (`PGSProcessed`,
  `SpectralProcessed`, `Registered`, `WebProcessed`).

**Raw/input datasets** (`PGSRaw`, `SpectralRaw`, …) are **never** deleted. A
missing id reports `not found` and the command exits non-zero.

> Equivalent programmatic call: `GraphDBConnection.delete_pipeline(pipeline_id)`,
> or over REST `DELETE /pipelines/{id}` /
> `HercClient.delete_pipeline(pipeline_id)`.
