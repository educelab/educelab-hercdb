"""Take test-run raw scans out of the graph's artifact coverage (DB-admin tool).

Some PGSRaw/SpectralRaw scans in the ground-truth CSVs were calibration or test
runs (resolution tests, focus checks, set-up flats, ...). The loader gave them a
``BELONGS_TO`` edge like any other scan, so the unattended dispatcher
(``find_unprocessed_datasets``) picked them as an artifact's newest complete
scan, processed them, and then treated the artifact as done.

This tool, driven by an exclusion CSV (``label, ds_uuid, path, eid, category``),
works in three steps, run in order:

``report``
    Read-only. Validates the CSV against the graph and writes the storage
    **delete manifest**: every processed dataset downstream of a listed scan
    (PGSProcessed/SpectralProcessed -> Registered -> WebProcessed), found by
    following ``INPUT``/``OUTPUT`` edges from the raw scan. Also lists the
    affected artifacts, pipelines that keep some stages, clean outputs that lose
    a tainted REG/WEB child (they need re-registering by hand), in-flight
    processes, and Processes whose raw input can no longer be traced.
``detach``
    Removes every ``BELONGS_TO`` from the listed scans and marks them
    ``excluded = true`` (with ``excluded_reason``, ``detached_from_eid``,
    ``detached_at``). The scan nodes stay, floating. ``INPUT`` edges are kept,
    so ``purge`` can still find what was derived from them.
``purge``
    Run after the files in the manifest have been deleted from storage. Deletes
    exactly the manifest's processed datasets plus the Processes that produced
    them, in one transaction, then any Pipeline left with no Process. It
    recomputes the downstream set first and refuses if it differs from the
    manifest, so it never deletes something that was not on the approved list.

Deletion is per stage, not per pipeline: one uber pipeline can have a PGS stage
fed by a test scan and a SPEC stage fed by a real one, and ``delete_pipeline``
would take the good SPEC output with it.

Queries run on the driver directly rather than through ``_run_query``, which
swallows errors into "no rows" -- for a destructive tool a failed query must
stop the run, not read as "nothing to do".

``scan_loader.py`` re-applies the detach after every load (``--exclude``), so a
``--replace`` reload does not quietly re-attach these scans.

Wired up as ``el-hercdb-exclude-test-scans``. Usage:

    uv run el-hercdb-exclude-test-scans report  [--csv ...] [--out-dir ./tmp]
    uv run el-hercdb-exclude-test-scans detach  [--csv ...]
    uv run el-hercdb-exclude-test-scans purge   [--csv ...] --manifest <dir>/delete_manifest.csv

The target database is whatever the config resolves to (``EDUCEDB_*`` env vars,
else ``~/.educedb``); every command prints it and asks for its host name before
writing.
"""
import argparse
import csv
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

from neo4j import RoutingControl

from educelab import hercdb
from educelab.hercdb import config

DEFAULT_CSV = 'input_data/excluded_test_scans.csv'
RAW_LABELS = ('PGSRaw', 'SpectralRaw')

# Processes that have not finished. Deleting one of these would leave a Slurm job
# writing to a path nobody records, so every write step refuses while any exist.
_FINISHED_STATUSES = ['completed', 'failed']

# One listed scan, matched on its MERGE key (label + uuid).
_MATCH_SCAN = """
    UNWIND $scans AS s
    MATCH (d) WHERE (d:PGSRaw OR d:SpectralRaw)
                AND s.label IN labels(d) AND d.uuid = s.uuid
"""

# Everything derived from the listed scans: raw -INPUT-> Process -OUTPUT->
# dataset -INPUT-> Process ... All four edge kinds point downstream, so a
# directed walk cannot climb back up into an unrelated input. Eight hops covers
# raw -> PGS -> REG -> WEB with room to spare.
_DOWNSTREAM = _MATCH_SCAN + """
    MATCH (d)-[:INPUT|OUTPUT*1..8]->(n)
"""

VALIDATE_QUERY = """
    UNWIND $scans AS s
    OPTIONAL MATCH (d) WHERE (d:PGSRaw OR d:SpectralRaw)
                         AND s.label IN labels(d) AND d.uuid = s.uuid
    OPTIONAL MATCH (d)-[:BELONGS_TO]->(e:EduceLabID)
    WITH s, d, collect(DISTINCT e.uuid) AS eids
    WITH s, collect({d: d, eids: eids}) AS hits
    RETURN s.label AS label, s.uuid AS uuid, s.path AS csv_path, s.eid AS csv_eid,
           s.category AS category,
           size([h IN hits WHERE h.d IS NOT NULL]) AS matches,
           head(hits).d.path AS db_path,
           head(hits).d.complete AS complete,
           head(hits).d.excluded AS excluded,
           head(hits).eids AS eids
"""

AFFECTED_QUERY = _MATCH_SCAN + """
    MATCH (d)-[:BELONGS_TO]->(e:EduceLabID)<-[:REPLACES*0..]-(active:EduceLabID)
    OPTIONAL MATCH (active)-[:ASSIGNED_TO]->(a)
    OPTIONAL MATCH (a)<-[:HAS]-(parent1)
    OPTIONAL MATCH (parent1)<-[:HAS]-(parent2)
    // Per artifact, not per uuid: an EduceLabID assigned to several artifacts
    // gets a row for each, so find_artifact_names_by_uuids (which keeps only
    // the most specific one) would not do here.
    RETURN s.category AS category, s.label AS label, d.path AS raw_path,
           d.complete AS complete, e.uuid AS belongs_to_uuid,
           active.uuid AS active_uuid, [l IN labels(a) WHERE l IN
           ['PHerc', 'Cornice', 'Pezzo']][0] AS artifact_type,
           CASE WHEN a:PHerc THEN a.displayName
                WHEN parent1:PHerc THEN parent1.displayName
                WHEN parent2:PHerc THEN parent2.displayName END AS pherc,
           CASE WHEN a:Cornice THEN a.displayName
                WHEN parent1:Cornice THEN parent1.displayName END AS cornice,
           CASE WHEN a:Pezzo THEN a.displayName END AS pezzo
"""

CLOSURE_QUERY = _DOWNSTREAM + """
    WITH n, collect(DISTINCT d.path) AS from_raw
    WHERE NOT n:Process
    OPTIONAL MATCH (proc:Process)-[:OUTPUT]->(n)
    OPTIONAL MATCH (proc)-[:STAGE_OF]->(pl:Pipeline)
    OPTIONAL MATCH (pl)-[:FOR]->(e:EduceLabID)
    RETURN head(labels(n)) AS label, n.path AS path, proc.stage AS stage,
           proc.status AS status, toString(proc.end_time) AS end_time,
           pl.pipeline_id AS pipeline_id, e.uuid AS artifact_uuid, from_raw
"""

IN_FLIGHT_QUERY = _DOWNSTREAM + """
    WITH DISTINCT n WHERE n:Process
                      AND NOT coalesce(n.status, '') IN $finished
    OPTIONAL MATCH (n)-[:STAGE_OF]->(pl:Pipeline)
    RETURN pl.pipeline_id AS pipeline_id, n.stage AS stage, n.status AS status,
           n.slurm_id AS slurm_id, toString(n.start_time) AS start_time
"""

MIXED_PIPELINES_QUERY = _DOWNSTREAM + """
    WITH collect(DISTINCT n) AS tainted
    UNWIND [p IN tainted WHERE p:Process] AS p
    MATCH (p)-[:STAGE_OF]->(pl:Pipeline)
    WITH DISTINCT pl, tainted
    MATCH (pl)<-[:STAGE_OF]-(proc:Process)
    WITH pl, tainted, collect(proc) AS procs
    WITH pl, [x IN procs WHERE x IN tainted | x.stage] AS deleted,
             [x IN procs WHERE NOT x IN tainted | x.stage] AS surviving
    WHERE size(surviving) > 0
    RETURN pl.pipeline_id AS pipeline_id, deleted AS deleted_stages,
           surviving AS surviving_stages
"""

# A REG has two inputs; when only one is tainted, the clean one survives but
# loses its registration (and webify) and has to be re-registered by hand --
# there is no REG work-list to pick it up.
NEEDS_REPROCESSING_QUERY = _DOWNSTREAM + """
    WITH collect(DISTINCT n) AS tainted
    UNWIND [p IN tainted WHERE p:Process AND p.stage = 'REG'] AS reg
    MATCH (clean)-[:INPUT]->(reg)
    WHERE NOT clean IN tainted
    OPTIONAL MATCH (reg)-[:STAGE_OF]->(:Pipeline)-[:FOR]->(e:EduceLabID)
    RETURN DISTINCT e.uuid AS artifact_uuid, head(labels(clean)) AS label,
           clean.path AS path
"""

# PGS/SPEC Processes with no raw scan feeding them. A ``scan_loader --replace``
# reload DETACH DELETEs raw nodes, INPUT edges included, so a test scan
# processed before the last reload cannot be traced from here.
PROVENANCE_GAP_QUERY = """
    MATCH (p:Process) WHERE p.stage IN ['PGS', 'SPEC'] AND NOT ()-[:INPUT]->(p)
    OPTIONAL MATCH (p)-[:STAGE_OF]->(pl:Pipeline)
    OPTIONAL MATCH (pl)-[:FOR]->(e:EduceLabID)
    OPTIONAL MATCH (p)-[:OUTPUT]->(o)
    RETURN pl.pipeline_id AS pipeline_id, p.stage AS stage, p.status AS status,
           e.uuid AS artifact_uuid, o.path AS output_path
"""

# Also run by scan_loader.py after every load. Matches on path too, so a CSV row
# that has drifted from the graph detaches nothing rather than the wrong node.
DETACH_QUERY = _MATCH_SCAN + """
    AND d.path = s.path
    MATCH (d)-[r:BELONGS_TO]->(e:EduceLabID)
    WITH d, s, collect(r) AS rels, collect(e.uuid) AS eids
    SET d.excluded = true,
        d.excluded_reason = s.category,
        d.detached_from_eid = eids,
        d.detached_at = datetime()
    FOREACH (r IN rels | DELETE r)
    RETURN count(d) AS detached, sum(size(rels)) AS edges_removed
"""

PURGE_QUERY = _DOWNSTREAM + """
    WITH collect(DISTINCT n) AS nodes
    UNWIND nodes AS n
    OPTIONAL MATCH (n)-[:STAGE_OF]->(pl:Pipeline)
    WITH nodes, collect(DISTINCT pl.pipeline_id) AS pipeline_ids
    WITH nodes, pipeline_ids,
         size([x IN nodes WHERE x:Process]) AS processes,
         size([x IN nodes WHERE NOT x:Process]) AS datasets
    FOREACH (x IN nodes | DETACH DELETE x)
    RETURN processes, datasets, pipeline_ids
"""

# Separate statement, same transaction, so it sees the Processes already gone.
# Scoped to the pipelines the purge touched: a Pipeline with no Process is also
# what a submission looks like between initialize_pipeline and its first stage.
EMPTY_PIPELINES_QUERY = """
    MATCH (pl:Pipeline) WHERE pl.pipeline_id IN $pipeline_ids
                          AND NOT ()-[:STAGE_OF]->(pl)
    WITH collect(pl) AS empty
    WITH empty, [pl IN empty | pl.pipeline_id] AS ids
    FOREACH (pl IN empty | DETACH DELETE pl)
    RETURN ids
"""


# --------------------------------------------------------------------------- #
# CSV input/output
# --------------------------------------------------------------------------- #

def load_exclusions(path: str) -> list[dict]:
    """Read the exclusion CSV into ``$scans`` parameter rows.

    De-duplicated on (label, uuid), the scan's identity in the graph -- the
    source list repeats a row. Raises ValueError on a label that is not a raw
    scan type, since every query here assumes one.
    """
    scans: dict[tuple, dict] = {}
    with open(path, newline='') as fh:
        for row in csv.DictReader(fh):
            label = (row.get('label') or '').strip()
            uuid = (row.get('ds_uuid') or '').strip()
            if not uuid:
                continue
            if label not in RAW_LABELS:
                raise ValueError(f"{path}: row for {uuid} has label {label!r}; "
                                 f"expected one of {', '.join(RAW_LABELS)}")
            scans[(label, uuid)] = {
                'label': label,
                'uuid': uuid,
                'path': (row.get('path') or '').strip(),
                'eid': (row.get('eid') or '').strip(),
                'category': (row.get('category') or '').strip(),
            }
    return list(scans.values())


def _write_csv(path: str, rows: list[dict], fields: list[str]) -> None:
    with open(path, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _cell(row.get(k)) for k in fields})


def _cell(value):
    if isinstance(value, (list, tuple)):
        return ';'.join(str(v) for v in value)
    return '' if value is None else value


def read_manifest(path: str) -> set[tuple]:
    """The (label, path) pairs a manifest approves for deletion."""
    with open(path, newline='') as fh:
        return {(r['label'], r['path'] or '') for r in csv.DictReader(fh)}


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #

def _read(driver, query: str, **params) -> list[dict]:
    records, _, _ = driver.execute_query(
        query, **params, database_='neo4j', routing_=RoutingControl.READ)
    return [r.data() for r in records]


def validate(driver, scans: list[dict]) -> list[dict]:
    """One row per CSV scan, with a ``problem`` string ('' when it checks out).

    A scan already detached (no ``BELONGS_TO`` left) is fine: that is what a
    second ``detach`` or a post-detach ``report`` sees.
    """
    rows = _read(driver, VALIDATE_QUERY, scans=scans)
    for r in rows:
        if r['matches'] == 0:
            problem = 'not found'
        elif r['matches'] > 1:
            problem = f"{r['matches']} nodes share this uuid"
        elif r['db_path'] != r['csv_path']:
            problem = 'path differs'
        elif r['eids'] and r['csv_eid'] not in r['eids']:
            problem = 'attached to a different EduceLabID'
        else:
            problem = ''
        r['problem'] = problem
        r['state'] = 'attached' if r['eids'] else 'floating'
    return rows


def downstream_datasets(driver_or_tx, scans: list[dict]) -> list[dict]:
    """The delete manifest: processed datasets derived from the listed scans."""
    if hasattr(driver_or_tx, 'execute_query'):
        return _read(driver_or_tx, CLOSURE_QUERY, scans=scans)
    return [r.data() for r in driver_or_tx.run(CLOSURE_QUERY, scans=scans)]


def in_flight(driver, scans: list[dict]) -> list[dict]:
    return _read(driver, IN_FLIGHT_QUERY, scans=scans, finished=_FINISHED_STATUSES)


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #

def detach(driver, scans: list[dict]) -> dict:
    """Remove the listed scans' BELONGS_TO edges and mark them excluded."""
    records, _, _ = driver.execute_query(DETACH_QUERY, scans=scans, database_='neo4j')
    r = records[0]
    return {'detached': r['detached'], 'edges_removed': r['edges_removed'] or 0}


class ManifestMismatch(Exception):
    """The downstream set no longer matches the approved manifest."""


def purge(driver, scans: list[dict], approved: set[tuple]) -> dict:
    """Delete the downstream Processes/datasets, then emptied Pipelines.

    One transaction: the downstream set is recomputed inside it and compared
    with ``approved``; any difference raises ManifestMismatch and rolls the
    whole thing back.
    """
    def work(tx):
        current = {(r['label'], r['path'] or '')
                   for r in downstream_datasets(tx, scans)}
        if current != approved:
            raise ManifestMismatch(
                f"{len(current - approved)} dataset(s) not in the manifest, "
                f"{len(approved - current)} manifest entr(y/ies) no longer found: "
                f"extra={sorted(current - approved)[:5]} "
                f"missing={sorted(approved - current)[:5]}")
        r = tx.run(PURGE_QUERY, scans=scans).single()
        if r is None:
            return {'processes': 0, 'datasets': 0, 'pipelines': []}
        removed = tx.run(EMPTY_PIPELINES_QUERY,
                         pipeline_ids=r['pipeline_ids']).single()['ids']
        return {'processes': r['processes'], 'datasets': r['datasets'],
                'pipelines': removed}

    with driver.session(database='neo4j') as session:
        return session.execute_write(work)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _host(uri: str) -> str:
    return urlparse(uri).hostname or uri


def _confirm(db, action: str) -> bool:
    host = _host(db.uri)
    print(f"\nAbout to {action} on {db.uri}")
    answer = input(f"Type the host name ({host}) to proceed: ").strip()
    if answer != host:
        print("Aborted.")
        return False
    return True


def _print_problems(rows: list[dict]) -> int:
    bad = [r for r in rows if r['problem']]
    for r in bad:
        print(f"  ! {r['label']} {r['uuid']} ({r['csv_path']}): {r['problem']}")
    return len(bad)


def _print_in_flight(rows: list[dict]) -> None:
    for r in rows:
        print(f"  ! {r['pipeline_id']} {r['stage']} status={r['status']} "
              f"slurm={r['slurm_id']}")


def cmd_report(db, scans, args) -> int:
    driver = db.driver
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    out = os.path.join(args.out_dir, f"exclude_test_scans_{_host(db.uri)}_{stamp}")
    os.makedirs(out, exist_ok=True)

    validation = validate(driver, scans)
    affected = _read(driver, AFFECTED_QUERY, scans=scans)
    manifest = downstream_datasets(driver, scans)
    flying = in_flight(driver, scans)
    mixed = _read(driver, MIXED_PIPELINES_QUERY, scans=scans)
    reprocess = _read(driver, NEEDS_REPROCESSING_QUERY, scans=scans)
    gaps = _read(driver, PROVENANCE_GAP_QUERY)

    names = db.find_artifact_names_by_uuids(
        {r['artifact_uuid'] for r in manifest + reprocess if r['artifact_uuid']})
    for r in manifest + reprocess:
        r['artifact'] = db._format_dataset_name(names.get(r['artifact_uuid']))
    for r in affected:
        r['artifact'] = db._format_dataset_name(r)
    affected.sort(key=lambda r: (r['artifact'], r['raw_path'] or ''))

    manifest.sort(key=lambda r: (r['artifact'], r['label'], r['path'] or ''))
    _write_csv(os.path.join(out, 'raw_validation.csv'), validation,
               ['category', 'label', 'uuid', 'csv_path', 'db_path', 'csv_eid',
                'eids', 'complete', 'state', 'excluded', 'problem'])
    _write_csv(os.path.join(out, 'affected_artifacts.csv'), affected,
               ['category', 'label', 'raw_path', 'complete', 'belongs_to_uuid',
                'active_uuid', 'artifact_type', 'artifact'])
    _write_csv(os.path.join(out, 'delete_manifest.csv'), manifest,
               ['label', 'path', 'stage', 'status', 'end_time', 'pipeline_id',
                'artifact_uuid', 'artifact', 'from_raw'])
    _write_csv(os.path.join(out, 'in_flight.csv'), flying,
               ['pipeline_id', 'stage', 'status', 'slurm_id', 'start_time'])
    _write_csv(os.path.join(out, 'mixed_pipelines.csv'), mixed,
               ['pipeline_id', 'deleted_stages', 'surviving_stages'])
    _write_csv(os.path.join(out, 'needs_reprocessing.csv'), reprocess,
               ['artifact_uuid', 'artifact', 'label', 'path'])
    _write_csv(os.path.join(out, 'provenance_gaps.csv'), gaps,
               ['pipeline_id', 'stage', 'status', 'artifact_uuid', 'output_path'])

    by_label: dict[str, int] = {}
    for r in manifest:
        by_label[r['label']] = by_label.get(r['label'], 0) + 1
    attached = sum(1 for r in validation if r['state'] == 'attached')

    print(f"Target: {db.uri}")
    print(f"Scans in CSV (deduplicated): {len(scans)}  "
          f"attached: {attached}  floating: {len(validation) - attached}")
    print(f"Affected artifact links:     {len(affected)}")
    print(f"Processed datasets to delete: {len(manifest)}  "
          + ', '.join(f"{k}={v}" for k, v in sorted(by_label.items())))
    print(f"Pipelines keeping some stages: {len(mixed)}")
    print(f"Clean outputs losing REG/WEB:  {len(reprocess)}")
    print(f"Untraceable PGS/SPEC processes (whole DB): {len(gaps)}")
    print(f"In-flight processes:           {len(flying)}")
    print(f"\nWrote reports to {out}/")

    status = 0
    if _print_problems(validation):
        print("CSV rows do not match the graph (see raw_validation.csv).")
        status = 1
    if flying:
        _print_in_flight(flying)
        print("Processes still running downstream of these scans (see in_flight.csv).")
        status = 1
    return status


def _preflight(db, scans) -> bool:
    """Refuse a write while the CSV disagrees with the graph or work is running."""
    ok = True
    if _print_problems(validate(db.driver, scans)):
        print("CSV rows do not match the graph; run `report` and fix them first.")
        ok = False
    flying = in_flight(db.driver, scans)
    if flying:
        _print_in_flight(flying)
        print("Processes still running downstream of these scans; "
              "wait for them or cancel them first.")
        ok = False
    return ok


def cmd_detach(db, scans, args) -> int:
    if not _preflight(db, scans):
        return 1
    attached = sum(1 for r in validate(db.driver, scans) if r['state'] == 'attached')
    print(f"{attached} of {len(scans)} scan(s) are still attached to an EduceLabID.")
    if attached == 0:
        print("Nothing to detach.")
        return 0
    if not args.yes and not _confirm(db, f"detach {attached} raw scan(s)"):
        return 1
    result = detach(db.driver, scans)
    print(f"Detached {result['detached']} scan(s), "
          f"removed {result['edges_removed']} BELONGS_TO edge(s).")
    return 0


def cmd_purge(db, scans, args) -> int:
    if not _preflight(db, scans):
        return 1
    approved = read_manifest(args.manifest)
    attached = sum(1 for r in validate(db.driver, scans) if r['state'] == 'attached')
    if attached:
        print(f"{attached} scan(s) are still attached; run `detach` before `purge`.")
        return 1
    if not approved:
        print("Manifest is empty; nothing to purge.")
        return 0
    print(f"Manifest lists {len(approved)} processed dataset(s). Make sure their "
          f"files are already gone from storage.")
    if not args.yes and not _confirm(
            db, f"delete {len(approved)} processed dataset(s) and their Processes"):
        return 1
    try:
        result = purge(db.driver, scans, approved)
    except ManifestMismatch as e:
        print(f"Refused, nothing deleted: {e}")
        print("Re-run `report`, review the new manifest, and purge with that.")
        return 1
    print(f"Deleted {result['datasets']} processed dataset(s), "
          f"{result['processes']} Process node(s), "
          f"{len(result['pipelines'])} emptied Pipeline(s)"
          + (f": {', '.join(result['pipelines'])}" if result['pipelines'] else '.'))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Detach test-run raw scans from their artifacts and purge "
                    "the processed datasets derived from them.")
    sub = parser.add_subparsers(dest='command', required=True)

    def add(name, help_text):
        p = sub.add_parser(name, help=help_text)
        p.add_argument('--csv', default=DEFAULT_CSV,
                       help=f"Exclusion list (default: {DEFAULT_CSV}).")
        return p

    p = add('report', 'Read-only: validate the list and write the delete manifest.')
    p.add_argument('--out-dir', default='./tmp',
                   help='Directory for the report folder (default: ./tmp).')
    p = add('detach', "Remove the scans' BELONGS_TO edges and mark them excluded.")
    p.add_argument('--yes', '-y', action='store_true',
                   help='Skip the host-name confirmation.')
    p = add('purge', 'Delete the manifest\'s processed datasets (after storage).')
    p.add_argument('--manifest', required=True,
                   help='delete_manifest.csv written by `report`.')
    p.add_argument('--yes', '-y', action='store_true',
                   help='Skip the host-name confirmation.')
    args = parser.parse_args()

    scans = load_exclusions(args.csv)
    if not scans:
        parser.error(f"{args.csv} lists no scans.")

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        print(f"Failed to connect to Neo4j at {db.uri}.", file=sys.stderr)
        sys.exit(1)

    command = {'report': cmd_report, 'detach': cmd_detach, 'purge': cmd_purge}
    sys.exit(command[args.command](db, scans, args))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
