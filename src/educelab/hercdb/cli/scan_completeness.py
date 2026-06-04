"""Scan-completeness report.

Walks every PHerc node and its hierarchy (Cornici, Pezzi) and produces two
CSV files describing scan coverage: one with every (artifact, UUID) row, and
one filtered to rows that need attention (missing/incomplete/no-UUID).
"""

import argparse
import csv
import re
import sys
from collections import namedtuple
from pathlib import Path

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.db import DatasetType


HEADER = [
    "PHerc",
    "Cornice",
    "Pezzo",
    "UUID",
    "PGS Status",
    "PGS Latest Complete Date",
    "PGS Path",
    "Spectral Status",
    "Spectral Latest Complete Date",
    "Spectral Path",
    "Institution",
]


StatusInfo = namedtuple("StatusInfo", "status date path")
BLANK_STATUS = StatusInfo(status="", date="", path="")


def natural_key(value):
    """Sort key so names order numerically (1, 2, ... 10, ... 100) instead of
    lexically (1, 10, 100, 2). Digit runs compare as ints; the surrounding text
    compares case-insensitively, so mixed names like "118a", "Cass.7", and
    "4 PHerc. s.n." still sort sensibly. re.split keeps text/number tokens at
    consistent positions, so every key compares text-to-text and int-to-int.
    """
    return [int(tok) if tok.isdigit() else tok.lower()
            for tok in re.split(r"(\d+)", value or "")]


def row_sort_key(row):
    """Order rows by PHerc, then Cornice, then Pezzo (columns 0, 1, 2)."""
    return (natural_key(row[0]), natural_key(row[1]), natural_key(row[2]))


def lookup_institution(db, pherc_display_name):
    """Return the PHerc-level CustodialInstitution name, or "" if none."""
    records, _, _ = db.find_node_type_connected_to_object_node(
        "PHerc", pherc_display_name, "CustodialInstitution"
    )
    if not records:
        return ""
    return records[0]["c"]["name"]


def _is_fully_complete(d):
    """A dataset counts as complete only if its `complete` flag is True AND it
    has no missing / zero-byte / short / bad-format files. Counts are stored as
    ints on the node; legacy nodes loaded before the count columns existed
    default to 0 (preserving the prior flag-only behavior for un-reloaded data).
    """
    if str(d.get("complete")) != "True":
        return False
    for key in ("missing_files", "zero_byte_files", "short_files", "bad_format_files"):
        try:
            if int(d.get(key, 0) or 0) != 0:
                return False
        except (TypeError, ValueError):
            return False
    return True


def classify(db, uuid, ds_type):
    """Return a StatusInfo describing whether `uuid` has a complete dataset
    of `ds_type`. Pools scans across the REPLACES chain so pre-replacement
    scans on retired predecessor UUIDs are included.
    """
    datasets = db.find_datasets_for_educelabid_with_predecessors(
        uuid, ds_type=ds_type
    )
    if not datasets:
        return StatusInfo("missing", "", "")
    complete = [d for d in datasets if _is_fully_complete(d)]
    if not complete:
        return StatusInfo("incomplete", "", "")
    newest = max(complete, key=lambda d: str(d.get("date_end", "")))
    return StatusInfo(
        "complete",
        str(newest.get("date_end", "")),
        str(newest.get("path", "")),
    )


def build_row(artifact_row, pgs, spec, institution):
    return [
        artifact_row["pherc"],
        artifact_row["cornice"],
        artifact_row["pezzo"],
        artifact_row["uuid"],
        pgs.status,
        pgs.date,
        pgs.path,
        spec.status,
        spec.date,
        spec.path,
        institution,
    ]


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate scan-completeness CSV reports across every PHerc in "
            "the Neo4j database. Writes two files: a full report (every "
            "artifact, every UUID) and an issues-only report (rows where "
            "any scan is missing/incomplete or the artifact has no UUID)."
        )
    )
    parser.add_argument(
        "--out-dir", default=".",
        help="Directory where the two CSV files are written (default: .).",
    )
    parser.add_argument(
        "--full-name", default="scan_completeness_full.csv",
        help="File name for the full report (default: scan_completeness_full.csv).",
    )
    parser.add_argument(
        "--issues-name", default="scan_completeness_issues.csv",
        help="File name for the issues-only report (default: scan_completeness_issues.csv).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    full_csv = out_dir / args.full_name
    issues_csv = out_dir / args.issues_name

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        print("Failed to connect to Neo4j.", file=sys.stderr)
        sys.exit(1)

    phercs = db.list_all_pherc_display_names()
    print(f"Walking {len(phercs)} PHerc nodes...")

    # Collect every row first so the output can be sorted numerically by
    # PHerc/Cornice/Pezzo before writing (the DB walk yields lexical order).
    all_rows = []
    for pherc in phercs:
        display_name = pherc["display_name"]
        institution = lookup_institution(db, display_name)
        artifact_rows = db.find_all_artifacts_and_educelabids_for_pherc(
            display_name
        )
        for artifact_row in artifact_rows:
            uuid = artifact_row["uuid"]
            if uuid:
                pgs = classify(db, uuid, DatasetType.PGSRaw)
                spec = classify(db, uuid, DatasetType.SpectralRaw)
            else:
                pgs = spec = BLANK_STATUS

            row = build_row(artifact_row, pgs, spec, institution)
            is_issue = (not uuid
                        or pgs.status != "complete"
                        or spec.status != "complete")
            all_rows.append((row, is_issue))

    all_rows.sort(key=lambda item: row_sort_key(item[0]))

    total_rows = issues_rows = 0
    with open(full_csv, "w", encoding="utf-8-sig", newline="") as f_all, \
            open(issues_csv, "w", encoding="utf-8-sig", newline="") as f_issues:
        writer_all = csv.writer(f_all)
        writer_iss = csv.writer(f_issues)
        writer_all.writerow(HEADER)
        writer_iss.writerow(HEADER)

        for row, is_issue in all_rows:
            writer_all.writerow(row)
            total_rows += 1
            if is_issue:
                writer_iss.writerow(row)
                issues_rows += 1

    print(f"Wrote {total_rows} rows to {full_csv}")
    print(f"Wrote {issues_rows} rows to {issues_csv}")


if __name__ == "__main__":
    main()
