import argparse
from datetime import datetime, timezone
import csv
from educelab.hercdb.loader import PhercGraphDatabaseLoader

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
if args.replace:
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
