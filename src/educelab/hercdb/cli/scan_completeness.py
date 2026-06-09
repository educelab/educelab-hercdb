"""Scan-completeness report.

Walks every PHerc node and its hierarchy (Cornici, Pezzi) and produces two
CSV files describing scan coverage: one with every (artifact, UUID) row, and
one filtered to rows that need attention (missing/incomplete/no-UUID).
"""

import argparse
import csv
import re
import sys
from collections import defaultdict, namedtuple
from pathlib import Path

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.db import DatasetType
from educelab.hercdb.cli.sample_uuid_check import (
    DEFAULT_PGS_CSV,
    DEFAULT_SPECTRAL_CSV,
    cross_check,
    load_scan_rows,
)


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

REVIEW_HEADER = ["Category", "Scan Type", "PHerc", "UUID", "Detail"]
# The review report flags sample-uuid *data errors* only (wrong / missing UUID).
# Deliberately excluded:
#   - INCOMPLETE_FILES: scanned-but-not-good artifacts already appear in the
#     issues CSV with an "incomplete" status; no need to duplicate them here.
#   - UNLINKED_UUID: minted UUIDs with no artifact — no physical object, out of
#     scope for "what needs scanning".
REVIEW_CATEGORIES = ["WRONG_SAMPLE_UUID", "ORPHAN_SAMPLE_UUID"]


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


def build_coverage(rows):
    """Group CSV scan rows by `sample uuid` and modality.

    Returns {sample_uuid: {"PGS": [ScanRow, ...], "Spectral": [...]}}. Only
    rows with a non-blank sample uuid contribute (blank ones can't attach to
    an artifact and surface separately in the cross-check).
    """
    coverage = defaultdict(lambda: {"PGS": [], "Spectral": []})
    for r in rows:
        if r.sample_uuid:
            coverage[r.sample_uuid][r.source].append(r)
    return coverage


def classify_from_csv(coverage, uuid, pred_map, modality):
    """CSV-backed counterpart to classify(): determine a modality's status for
    one artifact UUID from the scan CSVs, pooling scans across the UUID's
    REPLACES chain. Returns a StatusInfo.
    """
    pool = {uuid} | pred_map.get(uuid, set())
    scans = [s for u in pool for s in coverage.get(u, {}).get(modality, [])]
    if not scans:
        return StatusInfo("missing", "", "")
    complete = [s for s in scans if s.fully_complete]
    if not complete:
        return StatusInfo("incomplete", "", "")
    newest = max(complete, key=lambda s: s.date_end or "")
    return StatusInfo("complete", newest.date_end or "", newest.path or "")


def _scan_review_detail(anomaly):
    """Detail string for a WRONG/ORPHAN scan-side review row."""
    a = anomaly
    says = f"PHerc {a.path_pherc_raw}" + (
        f" / subdiv {a.path_subdiv}" if a.path_subdiv is not None else "")
    if a.resolved:
        actual = ("PHerc " + str(a.resolved["pherc"])
                  + (f" / Cornice {a.resolved['cornice']}" if a.resolved["cornice"] else "")
                  + (f" / Pezzo {a.resolved['pezzo']}" if a.resolved["pezzo"] else ""))
    else:
        actual = "no artifact (uuid not in DB / unassigned)"
    return f"path says {says} / resolves to {actual}; {a.path}"


def build_review_rows(db, rows):
    """Assemble the curated human-review rows from the cross-check: scan-side
    sample-uuid data errors only (wrong / missing UUID). Each row is a list
    matching REVIEW_HEADER: [Category, Scan Type, PHerc, UUID, Detail], where
    Scan Type is the modality of the offending scan (PGS / Spectral). Read-only."""
    out = []

    def add(category, scan_type, pherc, uuid, detail):
        out.append([category, scan_type, pherc or "", uuid or "", detail])

    result = cross_check(db, rows)
    for a in result.buckets["PHERC_MISMATCH"] + result.buckets["SUBDIV_MISMATCH"]:
        add("WRONG_SAMPLE_UUID", a.source, a.path_pherc_raw,
            a.sample_uuid, _scan_review_detail(a))
    for a in result.buckets["UUID_NOT_IN_DB"]:
        add("ORPHAN_SAMPLE_UUID", a.source, a.path_pherc_raw,
            a.sample_uuid, _scan_review_detail(a))

    out.sort(key=lambda r: (REVIEW_CATEGORIES.index(r[0]) if r[0] in REVIEW_CATEGORIES else 9,
                            natural_key(r[2])))
    return out


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
            "Generate scan-completeness CSV reports across every PHerc in the "
            "Neo4j database. Writes a full report (every artifact, every UUID) "
            "and an issues-only report (missing/incomplete or no-UUID). With "
            "--scans-from-csv, scan coverage is read directly from the scan "
            "CSVs (no DB scan-node load required) and a third review report of "
            "wrong/missing/inconsistent entries is also written."
        )
    )
    parser.add_argument(
        "--out-dir", default=".",
        help="Directory where the CSV files are written (default: .).",
    )
    parser.add_argument(
        "--full-name", default="scan_completeness_full.csv",
        help="File name for the full report (default: scan_completeness_full.csv).",
    )
    parser.add_argument(
        "--issues-name", default="scan_completeness_issues.csv",
        help="File name for the issues-only report (default: scan_completeness_issues.csv).",
    )
    parser.add_argument(
        "--review-name", default="scan_completeness_review.csv",
        help="File name for the human-review report (default: scan_completeness_review.csv). "
             "Only written with --scans-from-csv.",
    )
    parser.add_argument(
        "--scans-from-csv", action="store_true",
        help="Read PGS/Spectral coverage directly from the scan CSVs instead of "
             "loaded Neo4j scan nodes. Read-only on the DB; no scan-load needed.",
    )
    parser.add_argument(
        "--pgs-csv", default=DEFAULT_PGS_CSV,
        help=f"PGS scan CSV for --scans-from-csv (default: {DEFAULT_PGS_CSV}).",
    )
    parser.add_argument(
        "--spectral-csv", default=DEFAULT_SPECTRAL_CSV,
        help=f"Spectral scan CSV for --scans-from-csv (default: {DEFAULT_SPECTRAL_CSV}).",
    )
    parser.add_argument(
        "--no-review", action="store_true",
        help="Skip the review report (only relevant with --scans-from-csv).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    full_csv = out_dir / args.full_name
    issues_csv = out_dir / args.issues_name
    review_csv = out_dir / args.review_name

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        print("Failed to connect to Neo4j.", file=sys.stderr)
        sys.exit(1)

    # When sourcing coverage from the CSVs, read them once and prefetch the
    # REPLACES chains so a scan on a retired predecessor UUID still counts.
    coverage = pred_map = scan_rows = None
    if args.scans_from_csv:
        print("Reading scan coverage from CSVs (read-only; no scan-node load)...")
        scan_rows = load_scan_rows(args.pgs_csv, args.spectral_csv)
        coverage = build_coverage(scan_rows)
        pred_map = db.find_predecessor_uuid_map()

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
            if not uuid:
                pgs = spec = BLANK_STATUS
            elif args.scans_from_csv:
                pgs = classify_from_csv(coverage, uuid, pred_map, "PGS")
                spec = classify_from_csv(coverage, uuid, pred_map, "Spectral")
            else:
                pgs = classify(db, uuid, DatasetType.PGSRaw)
                spec = classify(db, uuid, DatasetType.SpectralRaw)

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

    # Curated human-review report (CSV-sourced mode only — the cross-check
    # needs the scan CSVs).
    if args.scans_from_csv and not args.no_review:
        review_rows = build_review_rows(db, scan_rows)
        with open(review_csv, "w", encoding="utf-8-sig", newline="") as f_rev:
            writer_rev = csv.writer(f_rev)
            writer_rev.writerow(REVIEW_HEADER)
            writer_rev.writerows(review_rows)
        counts = {}
        for r in review_rows:
            counts[r[0]] = counts.get(r[0], 0) + 1
        print(f"Wrote {len(review_rows)} rows to {review_csv}")
        for category in REVIEW_CATEGORIES:
            print(f"    {category:<20}: {counts.get(category, 0)}")


if __name__ == "__main__":
    main()
