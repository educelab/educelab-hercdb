import sys
import os
import argparse
from datetime import datetime as dt, timezone as tz
import uuid

from educelab import hercdb
from prompt_toolkit import print_formatted_text as print_fmt, HTML, prompt
from prompt_toolkit.validation import Validator
from natsort import natsorted

# Need to add PWD to PATH for slurm: https://stackoverflow.com/a/39574373
sys.path.append(os.getcwd())
from common import (DATA_DIR, LOG_DIR, PROCESSED_DIR_PGS, PROCESSED_DIR_SPEC,
                    PROCESSED_DIR_REG, PROCESSED_DIR_WEB, CPU_PARTITION,
                    SHARED_DIR, setup_logging, sbatch)
import pipeline_transfer as tx

db: hercdb.GraphDBConnection


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


def record_sort(r):
    ret = r['cr']['human_name']
    if r['pz'] is not None:
        ret += ', ' + r['pz']['human_name']
    return ret


def record_name(record):
    pherc = record['ph']['human_name']
    cr = record['cr']['human_name']
    is_scorze = 'Scorze' in cr or 'Scorza' in cr
    pz = ''
    if record['pz'] is not None:
        pz = f", Pz. {record['pz']['human_name']}"
    return f'P.Herc. {pherc}, {"" if is_scorze else "Cr. "}{cr}{pz}'


def select_sample():
    pherc = prompt('Enter P.Herc. number: ', validator=NotEmpty)

    records = db.list_cornici_pezzi(pherc)
    if len(records) == 0 or (
            len(records) == 1 and records[0]['cr'] == None and records[0]['pz'] == None):
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


def select_dataset(item, ds_type):
    ds_kwargs = {}
    if 'pz' in item.keys():
        ds_kwargs['pezzo'] = item['pz']['human_name']
    else:
        ds_kwargs['cornice'] = item['cr']['name']
    datasets = db.find_datasets(ds_type, item['pherc']['name'], **ds_kwargs)
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
    pgs = select_dataset(item, hercdb.PGSRawType)

    print()
    print('Selecting Spectral dataset...')
    spec = select_dataset(item, hercdb.SpectralRawType)

    # build default pipeline name
    pherc = item['pherc']['name']
    cr = item['cr']['name']
    crh = item['cr']['human_name']
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

    return {'pipeline_name': pname, 'pgs': pgs, 'spec': spec,
            'group_title': group_title, 'item_title': item_title}


def queue_pipeline(pipeline_name, pgs, spec, group_title, item_title,
                   dry_run=False, partition=None):
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

    return uber_job_id


def main():
    parser = argparse.ArgumentParser()
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

    print(f'Connecting to database...')
    hercdb.config.request_required()
    global db
    db = hercdb.connect()
    status = db.verify_connection()
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
