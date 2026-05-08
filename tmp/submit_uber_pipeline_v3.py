"""DB-only test version of submit_uber_pipeline.py.

All Slurm job submission, Globus transfer, and file I/O sections from
the original script are commented out (marked with '# disabled:').
Only the HercDB Client interactions remain active so we can test the
full pipeline DB workflow end-to-end without actually submitting jobs.

Key differences from the original:
- Uses HercClient (REST API) instead of direct GraphDBConnection
- No Slurm/Globus dependencies
- Fake slurm IDs for testing
- Simulates job completion and cleanup at the end

Usage:
    uv run tmp/submit_uber_pipeline_v3.py --host <host> --token <token>
"""

import sys
import argparse
from datetime import datetime as dt, timezone as tz
import uuid

from educelab.hercdb.client import HercClient
from prompt_toolkit import print_formatted_text as print_fmt, HTML, prompt
from prompt_toolkit.validation import Validator
from natsort import natsorted

# disabled: Slurm/Globus imports from the original are not needed for DB-only testing
# import os
# sys.path.append(os.getcwd())
# from common import (DATA_DIR, LOG_DIR, PROCESSED_DIR_PGS, PROCESSED_DIR_SPEC,
#                     PROCESSED_DIR_REG, PROCESSED_DIR_WEB, CPU_PARTITION,
#                     SHARED_DIR, setup_logging, sbatch)
# import pipeline_transfer as tx

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


def record_sort(r):
    # changed: 'human_name' -> 'displayName' (REST API uses displayName)
    ret = r['cr']['displayName']
    if r['pz'] is not None:
        ret += ', ' + r['pz']['displayName']
    return ret


def record_name(record):
    # changed: 'human_name' -> 'displayName' throughout
    pherc = record['ph']['displayName']
    cr = record['cr']['displayName']
    is_scorze = 'Scorze' in cr or 'Scorza' in cr
    pz = ''
    if record['pz'] is not None:
        pz = f", Pz. {record['pz']['displayName']}"
    return f'P.Herc. {pherc}, {"" if is_scorze else "Cr. "}{cr}{pz}'


def select_sample():
    pherc = prompt('Enter P.Herc. number: ', validator=NotEmpty)

    # changed: original uses db.list_cornici_pezzi(pherc) which returns a flat
    # list of records. HercClient.get_subdivisions() returns a dict with
    # 'pherc', 'cornici', and 'pezzi' keys, so we restructure below.
    try:
        subs = client.get_subdivisions(pherc)
    except Exception:
        subs = None

    if not subs:
        print('No trays found.')
        return None

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


def select_dataset(item, ds_type):
    # changed: 'human_name' -> 'displayName'; original uses item['cr']['name']
    # for cornice. Also, original calls db.find_datasets(ds_type, pherc_name, ...)
    # while HercClient.get_datasets() takes (pherc, ds_type, ...).
    ds_kwargs = {}
    if 'pz' in item.keys():
        ds_kwargs['pezzo'] = item['pz']['displayName']
    else:
        ds_kwargs['cornice'] = item['cr']['displayName']
    datasets = client.get_datasets(item['pherc']['displayName'], ds_type, **ds_kwargs)

    # sort by path, newest first
    datasets = natsorted(datasets, reverse=True, key=lambda x: x['path'])

    print(f'Found {len(datasets)} datasets (newest first, complete only):')
    pad = 3
    filtered = []
    for ds in datasets:
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
    # changed: original uses hercdb.PGSRawType enum; REST API takes string
    pgs = select_dataset(item, "PGSRaw")

    print()
    print('Selecting Spectral dataset...')
    # changed: original uses hercdb.SpectralRawType enum; REST API takes string
    spec = select_dataset(item, "SpectralRaw")

    # build default pipeline name
    # changed: original uses item['pherc']['name'] and item['cr']['name'];
    # REST API returns 'displayName', so we fall back to it when 'name' is absent
    pherc = item['pherc']['displayName']
    cr = item['cr'].get('name', item['cr']['displayName'])
    crh = item['cr']['displayName']
    cr = cr.replace('Scorza', 'Scorze')
    crh = crh.replace('Scorza', 'Scorze')
    is_scorze = 'Scorze' in cr or 'Scorze' in crh
    pname = f'PHerc{pad_int_str(pherc, 4)}Cr{pad_int_str(cr, 2)}'
    pname = ''.join(x if x.isalnum() else '_' for x in pname)

    # build default group and item titles
    group_title = f'P.Herc. {pherc}'
    item_title = f'{"" if is_scorze else "Cr. "}{crh}'

    print()
    pname = prompt(f'Edit pipeline name: ', default=pname)
    group_title = prompt('Edit group title: ', default=group_title)
    item_title = prompt('Edit item title: ', default=item_title)
    print()

    # added: pass artifact_uuid so queue_pipeline can register the pipeline in HercDB
    # Use the EduceLabID UUID (not the dataset UUID) to link the pipeline
    artifact_uuid = pgs['educelabid_uuid']

    return {'pipeline_name': pname, 'pgs': pgs, 'spec': spec,
            'group_title': group_title, 'item_title': item_title,
            'artifact_uuid': artifact_uuid}


def queue_pipeline(pipeline_name, pgs, spec, group_title, item_title,
                   artifact_uuid=None):
    # create uber job ID
    uber_job_id = 'uber-' + str(uuid.uuid4())[:8]

    # pipeline timestamp
    now = dt.now(tz.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")

    # disabled: Job ID log file (original writes slurm IDs to shared dir)
    # id_log_path = SHARED_DIR / f'{uber_job_id}.id'
    # id_log = id_log_path.open('w')

    # Register pipeline in HercDB
    client.initialize_pipeline(uber_job_id, artifact_uuid, now.isoformat())

    sample_title = f'{group_title}, {item_title}'
    title_line = f'{sample_title} [{uber_job_id}]'
    print(title_line)
    print('-' * len(title_line))
    print(f'Pipeline registered: {uber_job_id} -> {artifact_uuid}')

    # ---- disabled: Staging transfer (Globus, original submits via sbatch) ----
    # tx_id, _ = sbatch([...])
    # id_log.write(f'{tx_id}\n')
    # print(f'{tx_id: <10}{"Staging transfer": <32}')

    # ---- PGS: 3D reconstruction ----
    pgs_out_path = f'{pipeline_name}_recon_{ts}'
    # disabled: original submits PGS recon via sbatch
    # pgs_raw_path = DATA_DIR / pgs['path']
    # pgs_out_path = PROCESSED_DIR_PGS / pgs_out_name
    # pgs_id, _ = sbatch([...])
    # id_log.write(f'{pgs_id}\n')
    pgs_slurm_id = 'test-pgs'  # fake slurm ID for testing
    client.initialize_process(uber_job_id, "PGS", [pgs['path']],
                              pgs_out_path, pgs_slurm_id, now.isoformat())
    print(f'  PGS process registered (slurm_id: {pgs_slurm_id})')

    # ---- SPEC: Spectral enhancement ----
    spec_out_path = f'{pipeline_name}_spec_{ts}'
    # disabled: original submits spectral enhancement via sbatch
    # spec_raw_path = DATA_DIR / spec['path']
    # spec_out_path = PROCESSED_DIR_SPEC / spec_out_name
    # spec_id, _ = sbatch([...])
    # id_log.write(f'{spec_id}\n')
    spec_slurm_id = 'test-spec'  # fake slurm ID for testing
    client.initialize_process(uber_job_id, "SPEC", [spec['path']],
                              spec_out_path, spec_slurm_id, now.isoformat())
    print(f'  SPEC process registered (slurm_id: {spec_slurm_id})')

    # ---- REG: 2D->3D registration ----
    reg_out_path = f'{pipeline_name}_reg_{ts}'
    # disabled: original submits registration via sbatch
    # reg_id, _ = sbatch([...])
    # id_log.write(f'{reg_id}\n')
    reg_slurm_id = 'test-reg'  # fake slurm ID for testing
    client.initialize_process(uber_job_id, "REG",
                              [pgs_out_path, spec_out_path],
                              reg_out_path, reg_slurm_id, now.isoformat())
    print(f'  REG process registered (slurm_id: {reg_slurm_id})')

    # ---- WEB: Web prep ----
    prep_out_path = f'{pipeline_name}_webify_{ts}'
    # disabled: original submits web prep via sbatch
    # prep_id, _ = sbatch([...])
    # id_log.write(f'{prep_id}\n')
    web_slurm_id = 'test-web'  # fake slurm ID for testing
    client.initialize_process(uber_job_id, "WEB",
                              [reg_out_path],
                              prep_out_path, web_slurm_id, now.isoformat())
    print(f'  WEB process registered (slurm_id: {web_slurm_id})')

    # disabled: original archives each output via Globus transfer
    # for job_id, out_path, msg in (...):
    #     tx_id, _ = sbatch([...])
    #     id_log.write(f'{tx_id}\n')

    # disabled: close job ID log (not opened in this version)
    # id_log.close()

    # Print pipeline confirmation from HercDB
    confirmation = client.get_pipeline_confirmation(uber_job_id)
    print(f'\nPipeline {uber_job_id} status: {confirmation.get("status", "unknown")}')
    for stage in confirmation.get('stages', []):
        print(f'  {stage["proc_type"]}: {stage["status"]} (slurm {stage["slurm_id"]})')

    return uber_job_id


def simulate_completion(pipeline_id):
    """Mark all process stages as completed to test the full lifecycle."""
    print(f'\nSimulating job completion for pipeline {pipeline_id}...')
    now = dt.now(tz.utc)
    for proc_type in ["PGS", "SPEC", "REG", "WEB"]:
        result = client.update_process_status(
            pipeline_id, proc_type, "completed", now.isoformat())
        print(f'  {proc_type}: {result["status"]}')

    confirmation = client.get_pipeline_confirmation(pipeline_id)
    print(f'\nFinal pipeline status: {confirmation.get("status", "unknown")}')
    for stage in confirmation.get('stages', []):
        print(f'  {stage["proc_type"]}: {stage["status"]}')


def cleanup_pipeline(pipeline_id):
    """Delete the test pipeline and all its process/output dataset nodes.

    Input datasets (PGSRaw, SpectralRaw) are NOT deleted.
    """
    result = client.delete_pipeline(pipeline_id)
    print(f'\nPipeline {pipeline_id} deleted:')
    print(f'  Processes deleted:       {result["processes_deleted"]}')
    print(f'  Output datasets deleted: {result["output_datasets_deleted"]}')


def main():
    parser = argparse.ArgumentParser(
        description='DB-only test: pipeline workflow using HercClient (no Slurm)')
    parser.add_argument('--host', required=True,
                        help='Hostname or IP of the HercDB REST API server')
    parser.add_argument('--token', required=True,
                        help='Bearer token for API authentication')
    parser.add_argument('--port', type=int, default=8000,
                        help='REST API server port (default: 8000)')
    args = parser.parse_args()

    print(f'Connecting to HercDB REST API at {args.host}:{args.port}...')
    global client
    client = HercClient(host=args.host, token=args.token, port=args.port)
    try:
        client.check_token()
        status = True
    except Exception:
        status = False
    color = "ansigreen" if status else "ansired"
    print_fmt(HTML(f'Connected: <{color}>{str(status).lower()}</{color}>'))
    if not status:
        print('Connection failed.')
        sys.exit(1)
    print()

    # --- Build and register one pipeline ---
    p = build_pipeline()
    pipeline_id = queue_pipeline(**p)

    # --- Simulate all jobs completing ---
    input('\nPress Enter to simulate all jobs completing...')
    simulate_completion(pipeline_id)

    # --- Cleanup: delete test pipeline and its nodes ---
    # NOTE: This only deletes Pipeline, Process, and output dataset nodes.
    #       Input datasets (PGSRaw, SpectralRaw) are NOT touched.
    input('\nPress Enter to delete the test pipeline and its nodes...')
    cleanup_pipeline(pipeline_id)

    print('\nDone.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
