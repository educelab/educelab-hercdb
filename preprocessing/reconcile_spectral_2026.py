"""One-off reconciliation: backfill the 2026 spectral CSV's missing `sample uuid`
values from the 2023 spectral CSV, producing a ground-truth file for the loader.

Keyed on the scan `uuid` (the dataset's own uuid, a verified unique key in both files).
Keeps the exact 12 columns of the 2026 file (the dropped `sample uuid 2` column is NOT
restored — see the report it prints for the one secondary link that is intentionally lost).

Read-only on Neo4j; reads two CSVs and writes one.
"""

import csv
from pathlib import Path

INPUT_DIR = Path("input_data")
NEW_SPEC = INPUT_DIR / "spectral_datasets_20260601 1(in).csv"
OLD_SPEC = INPUT_DIR / "spectral-scans-20231108.csv"
OUT = INPUT_DIR / "spectral_datasets_20260601_reconciled.csv"


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    new_rows = load(NEW_SPEC)
    old_rows = load(OLD_SPEC)
    old_by_uuid = {(r.get("uuid") or "").strip(): r for r in old_rows}

    fieldnames = list(new_rows[0].keys())  # exact 12 columns of the 2026 file

    backfilled = 0
    blank_in_both = 0
    unrecoverable = []  # brand-new scans with no sample uuid and no 2023 row
    dropped_sample_uuid2 = []

    for row in new_rows:
        scan_uuid = (row.get("uuid") or "").strip()
        sample_uuid = (row.get("sample uuid") or "").strip()
        old = old_by_uuid.get(scan_uuid)

        if not sample_uuid:
            old_sample = (old.get("sample uuid") or "").strip() if old else ""
            if old_sample:
                row["sample uuid"] = old_sample
                backfilled += 1
            elif old is not None:
                blank_in_both += 1
            else:
                unrecoverable.append(row.get("path", ""))

        # Surface (but do NOT restore) any 2023 `sample uuid 2` value.
        if old:
            old_su2 = (old.get("sample uuid 2") or "").strip()
            if old_su2:
                dropped_sample_uuid2.append(
                    (scan_uuid, (row.get("sample uuid") or "").strip(), old_su2)
                )

    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    print(f"Wrote {len(new_rows)} rows -> {OUT}")
    print(f"  sample uuid backfilled from 2023:        {backfilled}")
    print(f"  still blank (also blank in 2023):        {blank_in_both}")
    print(f"  brand-new scans, no recoverable uuid:    {len(unrecoverable)}")
    print()
    print(f"  dropped 'sample uuid 2' secondary links: {len(dropped_sample_uuid2)}")
    for scan_uuid, su1, su2 in dropped_sample_uuid2:
        print(f"    scan {scan_uuid}: primary {su1} | LOST secondary {su2}")
    print()
    print("  brand-new unrecoverable paths:")
    for p in unrecoverable:
        print(f"    {p}")


if __name__ == "__main__":
    main()
