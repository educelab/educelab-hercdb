"""Cross-check the `sample uuid` in each scan CSV against the artifact encoded
in the scan's `path`, and load the scan CSVs into structured rows for the
read-only scan-completeness report.

Every scan path carries the artifact it was taken of, e.g.
    20220926/20220926_102542_PHerc0339Cr02_4638c071   -> PHerc 339, Cornice 2
The `sample uuid` column is the EduceLabID of the artifact the scan SHOULD be
linked to. A human-entered sample uuid that points at a different artifact (or
at no artifact at all) is a data error. This module parses the path, resolves
the sample uuid against Neo4j (EduceLabID-[:ASSIGNED_TO]->artifact), and reports
every disagreement.

Importable pieces (no DB writes — read queries only):
  - load_scan_rows(pgs_csv, spectral_csv) -> list[ScanRow]
  - cross_check(db, rows) -> CrossCheckResult

Standalone use writes a categorized text report:
  uv run el-hercdb-sample-uuid-check --out tmp/sample_uuid_check.txt

KNOWN LIMITATION: PHerc matching compares integer SETS, so it cannot distinguish
alpha-suffixed sub-scrolls such as 118a vs 118b — scan paths write only the bare
number ("118"), so the suffix is not available to validate against. The report
itself is unaffected: it attributes every scan by `sample uuid` -> the exact
Neo4j node (118a and 118b are distinct nodes with distinct UUIDs), so coverage
is never ambiguous. The cross-check just can't *catch* an 118a<->118b swap; the
report detail prints the full resolved displayName so a human can spot one.
"""

import argparse
import csv
import re
from collections import namedtuple
from pathlib import Path

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader as _L

# Ground-truth scan CSVs (PGS used directly; spectral reconciled against the
# 2023 file so 78 extra sample uuids are recovered, then hand-corrected — see
# docs/data_review_notes.md §5).
DEFAULT_PGS_CSV = "input_data/pgs_datasets_20260601(in).csv"
DEFAULT_SPECTRAL_CSV = "input_data/spectral_datasets_20260609_final.csv"
DEFAULT_OUT = Path("tmp/sample_uuid_check.txt")

# CSV count column -> node-style key (mirrors the scan node properties set by
# scan_loader.py; the loader itself is a run-on-import script, not importable).
_COUNT_COLS = {
    "missing files": "missing_files",
    "zero-byte files": "zero_byte_files",
    "short files": "short_files",
    "bad format files": "bad_format_files",
}
_COUNT_KEYS = tuple(_COUNT_COLS.values())

# A normalized scan row. `counts` is {node_key: int}; `fully_complete` applies
# the strict completeness rule (mirrors scan_completeness._is_fully_complete).
# `pherc_nums`/`pherc_raw`/`subdiv_num` are the artifact parsed from `path`.
ScanRow = namedtuple("ScanRow", [
    "source", "path", "scan_uuid", "sample_uuid",
    "complete", "counts", "date_end", "fully_complete",
    "pherc_nums", "pherc_raw", "subdiv_num",
])

# One cross-check disagreement. `resolved` is the {pherc,cornice,pezzo} the
# sample uuid actually points to (None if it points at no artifact).
Anomaly = namedtuple("Anomaly", [
    "source", "path", "scan_uuid", "sample_uuid",
    "path_pherc_raw", "path_subdiv", "resolved",
])

CrossCheckResult = namedtuple("CrossCheckResult", ["ok", "total", "buckets"])

BUCKET_ORDER = [
    "PHERC_MISMATCH",    # path PHerc num != uuid's PHerc num (high confidence)
    "SUBDIV_MISMATCH",   # PHerc matches, but path subdiv num != DB cornice/pezzo
    "CASETTA_MISMATCH",  # path casetta (Cass.N) != uuid's resolved casetta
    "UUID_NOT_IN_DB",    # sample uuid present but resolves to no artifact
    "NONNUMERIC_PHERC",  # path PHerc neither number nor casetta (test/null/other)
    "NO_PATH_ARTIFACT",  # path has no PHerc token (calibration/test scans)
    "BLANK_SAMPLE_UUID", # artifact path but no sample uuid given
]


# --------------------------------------------------------------------------- #
# parsing / normalization helpers
# --------------------------------------------------------------------------- #
def _norm(s):
    """Whitespace-insensitive, lowercased form for comparison."""
    return "".join((s or "").split()).lower()


def _normalize_complete(raw):
    """Collapse a CSV `complete` value to "True"/"False"/"unknown" (mirrors
    scan_loader.normalize_complete; duplicated because that module runs argparse
    on import and cannot be imported)."""
    norm = (raw or "").strip().lower()
    if norm == "true":
        return "True"
    if norm == "false":
        return "False"
    return "unknown"


def is_row_complete(complete_norm, counts):
    """Strict completeness rule for a CSV scan row: `complete` is "True" AND
    every file-count flag is 0. Mirrors scan_completeness._is_fully_complete."""
    if complete_norm != "True":
        return False
    return all(int(counts.get(k, 0) or 0) == 0 for k in _COUNT_KEYS)


def casetta_key(name):
    """Normalized canonical casetta key ('Cass. 20'/'Casetta 20'/'Cass.20' all
    -> 'cass.20'), or None if not a casetta. Lets us compare a path's casetta
    designation to a UUID's resolved artifact across spelling/spacing variants.
    Reuses the loader's casetta logic."""
    syns = _L._casetta_synonyms(name or "")
    return _norm(syns[0]) if syns else None


def nums(raw):
    """Set of all integers in a string ('1479/1417' -> {1479, 1417})."""
    return {int(n) for n in re.findall(r"\d+", str(raw))} if raw else set()


def leading_num(raw):
    """Leading integer of a displayName ('118a' -> 118, '2' -> 2), else None."""
    if not raw:
        return None
    m = re.match(r"0*(\d+)", str(raw).strip())
    return int(m.group(1)) if m else None


def parse_path_artifact(path):
    """Pull the artifact identity out of a scan path's last segment.

    Returns (pherc_nums, pherc_raw, subdiv_num):
      pherc_nums - set of every integer in the PHerc id, ignoring letter
                   suffixes ('0118' -> {118}) and capturing every member of a
                   range/combined name ('1417-1479' -> {1417, 1479}). None when
                   the id does not start with a number ('Cass. 78 s.n.').
      pherc_raw  - the raw PHerc id fragment as written (for reporting).
      subdiv_num - int from the first Cr/Cn marker (Cr02_ResTest -> 2), or None.
    All three are None when the segment has no PHerc token (calibration/test).

    Comparison is number-based on purpose: paths abbreviate the canonical name
    (path '118' vs DB '118a'), append junk after the id (Cr02_ResTest), use
    Cr/Cn inconsistently for Cornice vs Pezzo, and write combined scrolls
    differently ('1417-1479' vs DB '1479/1417'). The number SET survives that.
    """
    seg = path.rstrip("/").split("/")[-1]
    idx = seg.find("PHerc")
    if idx == -1:
        return None, None, None
    body = seg[idx + len("PHerc"):]
    # PHerc id = run of chars up to the first Cr/Cn subdivision marker.
    head = re.split(r"Cr|Cn", body, maxsplit=1)[0].strip(" _")
    pherc_raw = head or None
    pherc_nums = nums(head) if re.match(r"\s*\d", head) else None
    msub = re.search(r"(?:Cr|Cn)\s*0*(\d+)", body)
    subdiv_num = int(msub.group(1)) if msub else None
    return pherc_nums, pherc_raw, subdiv_num


def resolve_uuids(db, uuids):
    """Batch-resolve EduceLabID uuids to their artifact display names.

    Returns {uuid: {'pherc','cornice','pezzo'}} for uuids that resolve to an
    artifact; uuids absent from the dict have no EduceLabID / ASSIGNED_TO.
    Read-only.
    """
    if not uuids:
        return {}
    records, _, _ = db._run_query(
        """
        UNWIND $uuids AS u
        MATCH (e:EduceLabID {uuid:u})-[:ASSIGNED_TO]->(n)
        OPTIONAL MATCH (n)<-[:HAS]-(p1)
        OPTIONAL MATCH (p1)<-[:HAS]-(p2)
        WITH u,
             CASE
                 WHEN 'PHerc' IN labels(n) THEN n
                 WHEN 'PHerc' IN labels(p1) THEN p1
                 WHEN 'PHerc' IN labels(p2) THEN p2
             END AS pherc,
             CASE
                 WHEN 'Cornice' IN labels(n) THEN n
                 WHEN 'Cornice' IN labels(p1) THEN p1
             END AS cornice,
             CASE WHEN 'Pezzo' IN labels(n) THEN n END AS pezzo
        RETURN u AS uuid,
               pherc.displayName AS pherc,
               cornice.displayName AS cornice,
               pezzo.displayName AS pezzo
        """,
        uuids=list(uuids),
    )
    return {
        r["uuid"]: {"pherc": r["pherc"], "cornice": r["cornice"], "pezzo": r["pezzo"]}
        for r in records
    }


# --------------------------------------------------------------------------- #
# loading + cross-check
# --------------------------------------------------------------------------- #
def load_scan_rows(pgs_csv=DEFAULT_PGS_CSV, spectral_csv=DEFAULT_SPECTRAL_CSV):
    """Read both scan CSVs into normalized ScanRow tuples. A missing file is
    skipped with a printed note (so DB-only consumers still run)."""
    rows = []
    for source, fname in (("PGS", pgs_csv), ("Spectral", spectral_csv)):
        if not fname or not Path(fname).exists():
            print(f"  [skip] {source} CSV not found: {fname}")
            continue
        with open(fname, newline="") as fh:
            for row in csv.DictReader(fh):
                complete = _normalize_complete(row.get("complete"))
                counts = {key: int((row.get(col) or "").strip() or 0)
                          for col, key in _COUNT_COLS.items()}
                pn, pr, sub = parse_path_artifact(row.get("path") or "")
                rows.append(ScanRow(
                    source=source,
                    path=row.get("path") or "",
                    scan_uuid=(row.get("uuid") or "").strip(),
                    sample_uuid=(row.get("sample uuid") or "").strip(),
                    complete=complete,
                    counts=counts,
                    date_end=(row.get("datetime end") or "").strip(),
                    fully_complete=is_row_complete(complete, counts),
                    pherc_nums=pn,
                    pherc_raw=pr,
                    subdiv_num=sub,
                ))
    return rows


def _anom(r, art):
    return Anomaly(r.source, r.path, r.scan_uuid, r.sample_uuid,
                   r.pherc_raw, r.subdiv_num, art)


def cross_check(db, rows):
    """Bucket every scan row by how its sample uuid relates to the artifact its
    path names. Read-only. Returns a CrossCheckResult."""
    resolved = resolve_uuids(db, {r.sample_uuid for r in rows if r.sample_uuid})
    buckets = {k: [] for k in BUCKET_ORDER}
    ok = 0
    for r in rows:
        if r.pherc_raw is None:
            buckets["NO_PATH_ARTIFACT"].append(_anom(r, None))
            continue
        if not r.sample_uuid:
            buckets["BLANK_SAMPLE_UUID"].append(_anom(r, None))
            continue
        art = resolved.get(r.sample_uuid)
        if art is None:
            buckets["UUID_NOT_IN_DB"].append(_anom(r, None))
            continue
        if r.pherc_nums is None:
            # Descriptive PHerc id. If it's a casetta, validate against the
            # uuid's resolved artifact (casetta sits at PHerc level in some
            # data, cornice level in others) via canonical casetta keys.
            path_cass = casetta_key(r.pherc_raw)
            uuid_keys = {k for k in (casetta_key(art.get("pherc")),
                                     casetta_key(art.get("cornice"))) if k}
            if path_cass and uuid_keys:
                if path_cass in uuid_keys:
                    ok += 1
                else:
                    buckets["CASETTA_MISMATCH"].append(_anom(r, art))
            else:
                buckets["NONNUMERIC_PHERC"].append(_anom(r, art))
            continue
        db_pherc_nums = nums(art["pherc"])
        # PHercs agree when their number sets share any member (handles
        # range/combined names like path '1417-1479' vs DB '1479/1417').
        if db_pherc_nums and not (r.pherc_nums & db_pherc_nums):
            buckets["PHERC_MISMATCH"].append(_anom(r, art))
            continue
        db_cornice = leading_num(art["cornice"])
        db_pezzo = leading_num(art["pezzo"])
        # Subdivision matches if the path number equals the DB cornice OR pezzo
        # number (Cr/Cn is used for both). Only flag when both sides give one.
        if r.subdiv_num is not None and (db_cornice is not None or db_pezzo is not None) \
                and r.subdiv_num != db_cornice and r.subdiv_num != db_pezzo:
            buckets["SUBDIV_MISMATCH"].append(_anom(r, art))
        else:
            ok += 1
    return CrossCheckResult(ok=ok, total=len(rows), buckets=buckets)


# --------------------------------------------------------------------------- #
# standalone text report
# --------------------------------------------------------------------------- #
def _fmt(a):
    exp = f"PHerc {a.path_pherc_raw}" + (
        f" / subdiv {a.path_subdiv}" if a.path_subdiv is not None else "")
    if a.resolved:
        actual = ("PHerc " + str(a.resolved["pherc"])
                  + (f" / Cornice {a.resolved['cornice']}" if a.resolved["cornice"] else "")
                  + (f" / Pezzo {a.resolved['pezzo']}" if a.resolved["pezzo"] else ""))
    else:
        actual = "(not in DB)" if a.sample_uuid else "(no sample uuid)"
    return (f"[{a.source}] {a.path}\n"
            f"    sample uuid : {a.sample_uuid or '(blank)'}\n"
            f"    path says   : {exp}\n"
            f"    uuid resolves to: {actual}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Cross-check scan sample uuids against the artifact in each "
                    "scan path. Read-only; writes a categorized text report.")
    parser.add_argument("--pgs-csv", default=DEFAULT_PGS_CSV)
    parser.add_argument("--spectral-csv", default=DEFAULT_SPECTRAL_CSV)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    config.request_required()
    db = hercdb.connect()
    if not db.verify_connection():
        raise SystemExit("Failed to connect to Neo4j.")

    rows = load_scan_rows(args.pgs_csv, args.spectral_csv)
    result = cross_check(db, rows)
    buckets = result.buckets

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("Sample-UUID vs path artifact cross-check\n")
        f.write("=" * 60 + "\n\n")
        f.write("SUMMARY\n")
        f.write(f"  total scan rows      : {result.total}\n")
        f.write(f"  OK (path == uuid)    : {result.ok}\n")
        for k in BUCKET_ORDER:
            f.write(f"  {k:<20}: {len(buckets[k])}\n")
        for k in BUCKET_ORDER:
            f.write("\n" + "#" * 60 + "\n")
            f.write(f"# {k}  ({len(buckets[k])})\n")
            f.write("#" * 60 + "\n\n")
            for a in buckets[k]:
                f.write(_fmt(a) + "\n")

    print("SUMMARY")
    print(f"  total scan rows      : {result.total}")
    print(f"  OK (path == uuid)    : {result.ok}")
    for k in BUCKET_ORDER:
        print(f"  {k:<20}: {len(buckets[k])}")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
