import sys
import os
import argparse
from datetime import datetime as dt, timezone as tz
import uuid

# v2: Replaced direct Neo4j connection with HercClient REST API client
# v2-old: from educelab import hercdb
from educelab.hercdb.client import HercClient
from prompt_toolkit import print_formatted_text as print_fmt, HTML, prompt
from prompt_toolkit.validation import Validator
from natsort import natsorted

# Need to add PWD to PATH for slurm: https://stackoverflow.com/a/39574373
sys.path.append(os.getcwd())
from common import (DATA_DIR, LOG_DIR, PROCESSED_DIR_PGS, PROCESSED_DIR_SPEC,
                    PROCESSED_DIR_REG, PROCESSED_DIR_WEB, CPU_PARTITION,
                    SHARED_DIR, setup_logging, sbatch)
import pipeline_transfer as tx

# v2: Replaced GraphDBConnection with HercClient
# v2-old: db: hercdb.GraphDBConnection
client: HercClient


def in_range(min_val, max_val):
    def valid(s):
        try:
            v = int(s)
            return min_val <= v <= max_val
        except ValueError:
            return False

    return valid


def not_empty(s):
    return len(s) > 0


def y_or_n(s):
    return s.lower() in ('y', 'yes', 'n', 'no', '')


def str_to_bool(s):
    if s.lower() in ('y', 'yes'):
        return True
    if s.lower() in ('n', 'no', ''):
        return False
    else:
        raise RuntimeError(f'Not a valid bool str: {s}')


NotEmpty = Validator.from_callable(not_empty, error_message='No input provided')
IsYesNo = Validator.from_callable(y_or_n, error_message='Must be y/n')


def pad_int_str(s, pad):
    try:
        i = int(s)
        s = f'{i:0{pad}}'
    except ValueError:
        pass
    return s


# v2: Updated to use 'displayName' (REST API) instead of 'human_name' (Neo4j)
def record_sort(r):
    # v2-old: ret = r['cr']['human_name']
    ret = r['cr']['displayName']
    if r['pz'] is not None:
        # v2-old: ret += ', ' + r['pz']['human_name']
        ret += ', ' + r['pz']['displayName']
    return ret


# v2: Updated to use 'displayName' (REST API) instead of 'human_name' (Neo4j)
def record_name(record):
    # v2-old: pherc = record['ph']['human_name']
    # v2-old: cr = record['cr']['human_name']
    pherc = record['ph']['displayName']
    cr = record['cr']['displayName']
    is_scorze = 'Scorze' in cr or 'Scorza' in cr
    pz = ''
    if record['pz'] is not None:
        # v2-old: pz = f", Pz. {record['pz']['human_name']}"
        pz = f", Pz. {record['pz']['displayName']}"
    return f'P.Herc. {pherc}, {"" if is_scorze else "Cr. "}{cr}{pz}'


def select_sample():
    pherc = prompt('Enter P.Herc. number: ', validator=NotEmpty)

    # v2: Replaced db.list_cornici_pezzi() with client.get_subdivisions()
    # The REST API returns a single dict with 'pherc', 'cornici', 'pezzi' keys
    # instead of a flat list of {ph, cr, pz} records. We reconstruct the flat
    # record format here so the rest of the selection logic stays the same.
    # v2-old: records = db.list_cornici_pezzi(pherc)
    try:
        subs = client.get_subdivisions(pherc)
    except Exception:
        subs = None

    if not subs:
        print('No trays found.')
        return None

    # v2: Reconstruct flat records from the subdivisions response
    ph = subs['pherc']
    records = []
    for cr in subs.get('cornici', []):
        records.append({'ph': ph, 'cr': cr, 'pz': None})
    for pz in subs.get('pezzi', []):
        records.append({'ph': ph, 'cr': None, 'pz': pz})

    if len(records) == 0:
        print('No trays found.')
        return None

    print(f'Found trays: ')
    records = natsorted(records, key=record_sort)
    pad = 3
    for i, e in enumerate(records):
        print(f'{i + 1: {pad}}) {record_name(e)}')

    l, h = 1, len(records)
    validator = Validator.from_callable(in_range(l, h),
                                        error_message=f'Value not in range.')
    idx = int(prompt(f'Select tray [{l}-{h}]: ', validator=validator))
    item = records[idx - 1]
    print(f'Selected: {record_name(item)}')

    result = {'pherc': dict(item['ph']), 'cr': dict(item['cr'])}
    if item['pz'] is not None:
        result['pz'] = dict(item['pz'])

    return result


# v2: Updated to use client.get_datasets() and 'displayName' instead of 'human_name'/'name'
def select_dataset(item, ds_type):
    ds_kwargs = {}
    if 'pz' in item.keys():
        # v2-old: ds_kwargs['pezzo'] = item['pz']['human_name']
        ds_kwargs['pezzo'] = item['pz']['displayName']
    else:
        # v2-old: ds_kwargs['cornice'] = item['cr']['name']
        ds_kwargs['cornice'] = item['cr']['displayName']
    # v2: Replaced db.find_datasets() with client.get_datasets()
    # ds_type is now a string ("PGSRaw", "SpectralRaw") instead of an enum
    # v2-old: datasets = db.find_datasets(ds_type, item['pherc']['name'], **ds_kwargs)
    datasets = client.get_datasets(item['pherc']['displayName'], ds_type, **ds_kwargs)
    # TODO: return if len 0

    # sort by path, newest first
    datasets = natsorted(datasets, reverse=True, key=lambda x: x['path'])

    # select dataset
    print(f'Found {len(datasets)} datasets (newest first, complete only):')
    pad = 3
    filtered = []
    for i, ds in enumerate(datasets):
        if ds['complete'] == 'False':
            continue
        name = ds['path']
        ci = len(filtered)
        print(f'{ci + 1: {pad}}) {name} [{ds["uuid"][:8]}]')
        filtered.append(ds)

    l, h = 1, len(filtered)
    validator = Validator.from_callable(in_range(l, h),
                                        error_message=f'Value not in range.')
    idx = int(
        prompt(f'Select dataset [{l}-{h}]: ', validator=validator, default='1'))
    ds = filtered[idx - 1]
    print(f'Selected: {ds["path"]}')
    return ds


def build_pipeline():
    # Select the sample/object
    item = None
    while item is None:
        item = select_sample()

    print()
    print('Selecting PGS dataset...')
    # v2: Replaced hercdb.PGSRawType enum with "PGSRaw" string
    # v2-old: pgs = select_dataset(item, hercdb.PGSRawType)
    pgs = select_dataset(item, "PGSRaw")

    print()
    print('Selecting Spectral dataset...')
    # v2: Replaced hercdb.SpectralRawType enum with "SpectralRaw" string
    # v2-old: spec = select_dataset(item, hercdb.SpectralRawType)
    spec = select_dataset(item, "SpectralRaw")

    # build default pipeline name
    # v2: Using 'displayName' instead of 'name'/'human_name'
    # v2-old: pherc = item['pherc']['name']
    # v2-old: cr = item['cr']['name']
    # v2-old: crh = item['cr']['human_name']
    pherc = item['pherc']['displayName']
    cr = item['cr'].get('name', item['cr']['displayName'])
    crh = item['cr']['displayName']
    cr = cr.replace('Scorza', 'Scorze')
    crh = crh.replace('Scorza', 'Scorze')
    is_scorze = 'Scorze' in cr or 'Scorze' in crh
    pname = f'PHerc{pad_int_str(pherc, 4)}Cr{pad_int_str(cr, 2)}'
    pname = ''.join(x if x.isalnum() else '_' for x in pname)

    # build default group and item titles
    # TODO: Handle pezzi
    group_title = f'P.Herc. {pherc}'
    item_title = f'{"" if is_scorze else "Cr. "}{crh}'

    print()
    pname = prompt(f'Edit pipeline name: ', default=pname)
    group_title = prompt('Edit group title: ', default=group_title)
    item_title = prompt('Edit item title: ', default=item_title)
    print()

    # v2-added: Pass artifact UUID (from the PGS dataset) for pipeline DB registration
    artifact_uuid = pgs['uuid']

    return {'pipeline_name': pname, 'pgs': pgs, 'spec': spec,
            'group_title': group_title, 'item_title': item_title,
            'artifact_uuid': artifact_uuid}


def queue_pipeline(pipeline_name, pgs, spec, group_title, item_title,
                   artifact_uuid=None, dry_run=False, partition=None):
    if partition is None:
        partition = CPU_PARTITION

    # create uber job ID
    uber_job_id = 'uber-' + str(uuid.uuid4())[:8]

    # job id log
    if not dry_run:
        id_log_path = SHARED_DIR / f'{uber_job_id}.id'
        id_log = id_log_path.open('w')

    # pipeline timestamp
    now = dt.now(tz.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")

    # v2-added: Register pipeline in HercDB
    if not dry_run:
        client.initialize_pipeline(uber_job_id, artifact_uuid, now.isoformat())
        print(f'Pipeline registered: {uber_job_id} -> {artifact_uuid}')

    sample_title = f'{group_title}, {item_title}'
    title_line = f'{sample_title} [{uber_job_id}]'
    print(title_line)
    print('-' * len(title_line))

    # Stage data
    if not dry_run:
        tx_id, _ = sbatch([
            f'-p', partition,
            f'--mail-type=FAIL',
            f'--export=ALL,UBER_JOB_ID={uber_job_id}',
            f'--job-name={uber_job_id}-stage',
            f'--output={str(LOG_DIR)}/%x.%j.out.txt',
            '--time=00:20:00',
            'pipeline_transfer.py',
            '-s', 'gemini1-2',
            '-d', 'lcc',
            '--label', f'Data staging ({uber_job_id})',
            '--log-level', 'debug',
            pgs['path'], spec['path']
        ])
        id_log.write(f'{tx_id}\n')
    else:
        tx_id = '######'
    print(f'{tx_id: <10}{"Staging transfer": <32}')

    # Queue 3D recon job
    pgs_raw_path = DATA_DIR / pgs['path']
    pgs_out_name = f'{pipeline_name}_recon_{ts}'
    pgs_out_path = PROCESSED_DIR_PGS / pgs_out_name
    if not dry_run:
        pgs_id, _ = sbatch([
            f'-p', partition,
            f'--mail-type=FAIL',
            f'--export=ALL,UBER_JOB_ID={uber_job_id}',
            f'--job-name={uber_job_id}-recon',
            f'--output={str(LOG_DIR)}/%x.%j.out.txt',
            f'--dependency=afterok:{tx_id}',
            '--cpus-per-task=32', '--mem=0',
            '--time=12:00:00',
            'pipeline_recon.py',
            '-i', str(pgs_raw_path),
            '-n', pgs_out_name,
        ])
        id_log.write(f'{pgs_id}\n')
        # v2-added: Register PGS process in HercDB
        client.initialize_process(uber_job_id, "PGS", [pgs['path']],
                                  str(pgs_out_path), str(pgs_id), now.isoformat())
    else:
        pgs_id = '######'
    print(f'{pgs_id: <10}{"3D reconstruction": <32}{pgs_out_path.name}')

    # Queue spectral enhancement job
    spec_raw_path = DATA_DIR / spec['path']
    spec_out_name = f'{pipeline_name}_spec_{ts}'
    spec_out_path = PROCESSED_DIR_SPEC / spec_out_name
    if not dry_run:
        spec_id, _ = sbatch([
            f'-p', partition,
            f'--mail-type=FAIL',
            f'--export=ALL,UBER_JOB_ID={uber_job_id}',
            f'--job-name={uber_job_id}-spec',
            f'--output={str(LOG_DIR)}/%x.%j.out.txt',
            f'--dependency=afterok:{tx_id}',
            '--cpus-per-task=16',
            '--time=00:10:00',
            'pipeline_spectral.py',
            '-i', str(spec_raw_path),
            '-n', spec_out_name,
        ])
        id_log.write(f'{spec_id}\n')
        # v2-added: Register SPEC process in HercDB
        client.initialize_process(uber_job_id, "SPEC", [spec['path']],
                                  str(spec_out_path), str(spec_id), now.isoformat())
    else:
        spec_id = '######'
    print(f'{spec_id: <10}{"Spectral enhancement": <32}{spec_out_path.name}')

    # Queue registration job
    reg_out_name = f'{pipeline_name}_reg_{ts}'
    reg_out_path = PROCESSED_DIR_REG / reg_out_name
    if not dry_run:
        reg_id, _ = sbatch([
            f'-p', partition,
            f'--mail-type=FAIL',
            f'--export=ALL,UBER_JOB_ID={uber_job_id}',
            f'--job-name={uber_job_id}-reg',
            f'--output={str(LOG_DIR)}/%x.%j.out.txt',
            f'--dependency=afterok:{pgs_id}:{spec_id}',
            '--cpus-per-task=16',
            '--time=00:20:00',
            'pipeline_registration.py',
            '--pgs-dir', str(pgs_out_path),
            '--spec-dir', str(spec_out_path),
            '--name', reg_out_name,
            '--output-stem', pipeline_name,
        ])
        id_log.write(f'{reg_id}\n')
        # v2-added: Register REG process in HercDB
        client.initialize_process(uber_job_id, "REG",
                                  [str(pgs_out_path), str(spec_out_path)],
                                  str(reg_out_path), str(reg_id), now.isoformat())
    else:
        reg_id = '######'
    print(f'{reg_id: <10}{"2D->3D registration": <32}{reg_out_path.name}')

    # Queue webify prep job
    prep_out_name = f'{pipeline_name}_webify_{ts}'
    prep_out_path = PROCESSED_DIR_WEB / prep_out_name
    if not dry_run:
        prep_id, _ = sbatch([
            f'-p', partition,
            f'--mail-type=FAIL',
            f'--export=ALL,UBER_JOB_ID={uber_job_id}',
            f'--job-name={uber_job_id}-webify',
            f'--output={str(LOG_DIR)}/%x.%j.out.txt',
            f'--dependency=afterok:{reg_id}',
            '--cpus-per-task=16',
            '--time=00:20:00',
            'pipeline_webify.py',
            '--spec-dir', str(spec_out_path),
            '--reg-dir', str(reg_out_path),
            '--name', prep_out_name,
            '--group-title', group_title,
            '--item-title', item_title,
        ])
        id_log.write(f'{prep_id}\n')
        # v2-added: Register WEB process in HercDB
        client.initialize_process(uber_job_id, "WEB",
                                  [str(reg_out_path)],
                                  str(prep_out_path), str(prep_id), now.isoformat())
    else:
        prep_id = '######'
    print(f'{prep_id: <10}{"Web prep": <32}{prep_out_path.name}')

    # Data archive jobs
    for job_id, out_path, msg in (
            (pgs_id, pgs_out_path, 'Archive 3D reconstruction'),
            (spec_id, spec_out_path, 'Archive spectral enhancements'),
            (reg_id, reg_out_path, 'Archive registration results'),
            (prep_id, prep_out_path, 'Archive web-friendly versions')):
        if not dry_run:
            tx_id, _ = sbatch([
                f'-p', partition,
                f'--mail-type=FAIL',
                f'--export=ALL,UBER_JOB_ID={uber_job_id}',
                f'--job-name={uber_job_id}-archive',
                f'--output={str(LOG_DIR)}/%x.%j.out.txt',
                f'--dependency=afterok:{job_id}',
                '--time=00:20:00',
                'pipeline_transfer.py',
                '-s', 'lcc',
                '-d', 'gemini1-2',
                '--label', f'{msg} ({uber_job_id})',
                '--log-level', 'debug',
                str(out_path.relative_to(DATA_DIR))
            ])
            id_log.write(f'{tx_id}\n')
        else:
            tx_id = '######'
        print(f'{tx_id: <10}{msg}')

    if not dry_run:
        id_log.close()

        # v2-added: Print pipeline confirmation from HercDB
        confirmation = client.get_pipeline_confirmation(uber_job_id)
        print(f'\nPipeline {uber_job_id} status: {confirmation.get("status", "unknown")}')
        for stage in confirmation.get('stages', []):
            print(f'  {stage["proc_type"]}: {stage["status"]} (slurm {stage["slurm_id"]})')

    return uber_job_id


def main():
    parser = argparse.ArgumentParser()
    # v2: Added --host and --token arguments for HercClient connection
    parser.add_argument('--host', required=True,
                        help='Hostname or IP of the HercDB REST API server')
    parser.add_argument('--token', required=True,
                        help='Bearer token for API authentication')
    parser.add_argument('--port', type=int, default=8000,
                        help='REST API server port (default: 8000)')
    parser.add_argument('--list-pipeline-ids',
                        action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Report job information but don\'t queue jobs.')
    parser.add_argument('--cpu-partition', default=CPU_PARTITION,
                        help='Queue jobs on provided partition')
    parser.add_argument('--log-level',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR',
                                 'CRITICAL'], type=str.upper, default='INFO')
    args = parser.parse_args()
    setup_logging(args.log_level, exclude=['neo4j', 'asyncio', 'globus_sdk'])

    # v2: Replaced direct Neo4j connection with HercClient REST API client
    # v2-old: print(f'Connecting to database...')
    # v2-old: hercdb.config.request_required()
    # v2-old: global db
    # v2-old: db = hercdb.connect()
    # v2-old: status = db.verify_connection()
    print(f'Connecting to HercDB REST API at {args.host}:{args.port}...')
    global client
    client = HercClient(host=args.host, token=args.token, port=args.port)
    try:
        client.check_token()
        status = True
    except Exception:
        status = False
    color = 'ansigreen' if status else 'ansired'
    print_fmt(HTML(f'Connected: <{color}>{str(status).lower()}</{color}>'))
    if not status:
        print('Connection failed.')
        sys.exit(1)
    print()

    pipelines = []
    get_pipeline = True
    while get_pipeline:
        p = build_pipeline()
        pipelines.append(p)

        print('Pipeline queue')
        print('--------------')
        for i, p in enumerate(pipelines):
            print(f'{i + 1: 3}) {p["group_title"]}, {p["item_title"]}')
        print()
        c = prompt('Add another item to queue (yN)? ',
                   validator=IsYesNo)
        get_pipeline = str_to_bool(c)

    # make sure globus has a token
    tx.login_flow([v['uuid'] for v in tx.ENDPOINTS.values()])

    # set up common dirs
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_DIR.mkdir(parents=True, exist_ok=True)

    # queue pipeline
    print('Queueing pipelines...')
    pipeline_ids = []
    for p in pipelines:
        print()
        pid = queue_pipeline(**p,
                             dry_run=args.dry_run,
                             partition=args.cpu_partition)
        pipeline_ids.append(pid)

    if args.list_pipeline_ids:
        print()
        print('Pipeline IDs')
        print('------------')
        for pid in pipeline_ids:
            print(pid)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)


# =========================================================================
#  TODO: Post-submission status updates
#
#  The code above only submits jobs and registers them in HercDB as
#  "submitted". When a Slurm job finishes (via epilog, callback, or a
#  separate monitoring script), the following HercClient calls should be
#  made to update the pipeline status in HercDB:
#
#  --- Mark a process as completed ---
#  client.update_process_status(
#      pipeline_id=uber_job_id,
#      proc_type="PGS",          # or "SPEC", "REG", "WEB"
#      status="completed",
#      end_datetime=datetime.now().isoformat(),
#  )
#
#  --- Mark a process as failed ---
#  client.update_process_status(
#      pipeline_id=uber_job_id,
#      proc_type="PGS",          # or "SPEC", "REG", "WEB"
#      status="failed",
#      end_datetime=datetime.now().isoformat(),
#  )
#
#  --- Check final pipeline state ---
#  confirmation = client.get_pipeline_confirmation(uber_job_id)
#  print(confirmation["status"])   # "completed", "failed", "running", etc.
#  for stage in confirmation["stages"]:
#      print(stage["proc_type"], stage["status"])
#
#  --- Delete a pipeline and all its nodes (ONLY IF NEEDED TO FIX ERRORS!) ---
#  result = client.delete_pipeline(uber_job_id)
#  print(f"Deleted {result['processes_deleted']} processes, "
#        f"{result['output_datasets_deleted']} output datasets")
# =========================================================================
