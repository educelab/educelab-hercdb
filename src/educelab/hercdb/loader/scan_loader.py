import argparse
from datetime import datetime, timezone
import csv
from educelab.hercdb.loader import PhercGraphDatabaseLoader
from educelab.hercdb.cli.exclude_test_scans import DETACH_QUERY, load_exclusions
from educelab.hercdb.loader import extra_scan_links

parser = argparse.ArgumentParser(description='Load scan data into Neo4j')
parser.add_argument('--negatives', default='input_data/negatives.csv',
                    help='Path to negatives CSV file (default: input_data/negatives.csv)')
parser.add_argument('--photogrammetry', default='input_data/pgs_datasets_20260601(in).csv',
                    help='Path to photogrammetry scans CSV file (default: 2026 PGS ground-truth)')
parser.add_argument('--spectral', default='input_data/spectral_datasets_20260609_final.csv',
                    help='Path to spectral scans CSV file (default: 2026 spectral ground-truth)')
parser.add_argument('--replace', action=argparse.BooleanOptionalAction, default=True,
                    help='Delete all existing PGSRaw/SpectralRaw nodes before loading '
                         '(default: --replace). Use --no-replace to merge into existing data.')
parser.add_argument('--exclude', default='input_data/excluded_test_scans.csv',
                    help='Test-run scans to load without a BELONGS_TO edge (see '
                         'el-hercdb-exclude-test-scans). Default: '
                         'input_data/excluded_test_scans.csv; pass "" to skip.')
parser.add_argument('--extra-links', default=extra_scan_links.DEFAULT_PATH,
                    help='Scans that image more than one tray: extra BELONGS_TO links to add '
                         f'after loading (#43). Default: {extra_scan_links.DEFAULT_PATH}; '
                         'pass "" to skip.')
args = parser.parse_args()

negatives_file = args.negatives
photogrammetry_file = args.photogrammetry
spectral_file = args.spectral

loader = PhercGraphDatabaseLoader()
loader.verify_conn()


def to_int(raw):
    """Parse a CSV count column to int; blank -> 0."""
    raw = (raw or "").strip()
    return int(raw) if raw else 0

def clean_datetime(dt_str):
    if not dt_str:
        return None
    # Remove " (UTC)" if present and parse the datetime
    clean_string = dt_str.replace(" (UTC)", "")
    dt = datetime.strptime(clean_string, "%m/%d/%Y, %H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)
    return dt if dt else None


def normalize_complete(raw):
    """Normalize a CSV `complete` value to "True", "False", or "unknown".

    Case-insensitive so input variants ("TRUE", "True", "true") all collapse
    to the canonical string the downstream Cypher checks for. Returns a
    non-empty string so callers can rely on the loader's `if complete:`
    guard always firing — re-runs overwrite the property in either direction.
    """
    norm = raw.strip().lower() if raw else ""
    if norm == "true":
        return "True"
    if norm == "false":
        return "False"
    return "unknown"


# First load the negatives file
with open(negatives_file, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        image_num = row['Image number']
        uuid = row['UUID'] # may be None
        neg_series = row['Negatives series'] if row['Negatives series'] else "unknown"
        pherc = row['PHerc.']
        cornice = row['cornice']
        neg_storage = row['Storage location'] if row['Storage location'] else "unknown"
        
        if image_num:
            loader.add_flatbed_scan_node(
                image_num=image_num,
                uuid=uuid,
                pherc=pherc,
                cornice=cornice,
                neg_series=neg_series,
                neg_storage=neg_storage
            )

# Wipe existing scan nodes before reload so changed paths / dropped rows can't
# leave stale or duplicate PGSRaw/SpectralRaw nodes behind (negatives untouched).
# Reviewers' release decisions live on the scan nodes, so save them before the
# wipe and put them back after the load.
saved_release_states = []
if args.replace:
    saved_release_states = loader.get_scan_release_states()
    loader.delete_all_scan_nodes()
    print("Deleted existing PGSRaw/SpectralRaw nodes.")

with open(photogrammetry_file, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        path = row['path']
        scan_uuid = row['uuid']
        datetime_start = clean_datetime(row['datetime start'])
        datetime_end = clean_datetime(row['datetime end']) if row['datetime end'] else None
        complete = normalize_complete(row['complete'])
        sample_uuid = row['sample uuid'] if row['sample uuid'] else None # may be None

        loader.add_pgs_raw_node(
            pgs_path=path,
            scan_uuid=scan_uuid,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            complete=complete,
            sample_uuid=sample_uuid,
            file_count=to_int(row['file count']),
            missing_files=to_int(row['missing files']),
            zero_byte_files=to_int(row['zero-byte files']),
            short_files=to_int(row['short files']),
            bad_format_files=to_int(row['bad format files'])
        )

with open(spectral_file, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        path = row['path']
        scan_uuid = row['uuid']
        datetime_start = clean_datetime(row['datetime start'])
        datetime_end = clean_datetime(row['datetime end']) if row['datetime end'] else None
        complete = normalize_complete(row['complete'])
        sample_uuid = row['sample uuid'] if row['sample uuid'] else None # may be None

        loader.add_spectral_raw_node(
            spectral_path=path,
            scan_uuid=scan_uuid,
            datetime_start=datetime_start,
            datetime_end=datetime_end,
            complete=complete,
            sample_uuid=sample_uuid,
            file_count=to_int(row['file count']),
            missing_files=to_int(row['missing files']),
            zero_byte_files=to_int(row['zero-byte files']),
            short_files=to_int(row['short files']),
            bad_format_files=to_int(row['bad format files'])
        )

if saved_release_states:
    loader.restore_scan_release_states(saved_release_states)
    print(f"Restored release flags on {len(saved_release_states)} scans.")

# Test-run scans are in the ground-truth CSVs with a sample uuid, so the loads
# above attached them like any other scan. Detach them again, or a --replace
# reload would hand them back to the dispatcher.
if args.exclude:
    excluded = load_exclusions(args.exclude)
    records, _, _ = loader._run_query(DETACH_QUERY, scans=excluded)
    if records is None:
        raise SystemExit(f"Failed to detach the scans listed in {args.exclude}.")
    print(f"Detached {records[0]['detached']} of {len(excluded)} excluded "
          f"test scan(s) listed in {args.exclude}.")

# A capture holding two trays has one `sample uuid` in the CSV, so it reached
# only one of them. Add the other links from the hand-kept list.
if args.extra_links:
    links = extra_scan_links.load_links(args.extra_links)
    print(f"Added {extra_scan_links.apply(loader.driver, links)} extra scan link(s) "
          f"listed in {args.extra_links}.")
