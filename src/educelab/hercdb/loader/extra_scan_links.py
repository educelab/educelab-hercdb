"""Hand-kept extra BELONGS_TO links for scans that image more than one tray (#43).

A scan CSV row carries one `sample uuid`, so a capture that holds two trays in
one view reaches only one of them. The rest are listed in
`input_data/extra_scan_links.csv` (`label, scan_uuid, eid, note`).
`scan_loader` re-applies the list after every load, since `--replace` deletes
and recreates the scan nodes. First case: the whole-cornice spectral scan
`ce015560` (`PHerc0076Cr05 LR`) shows both 76 Cr 05 trays, Left and Right.

Run on its own to link an existing graph without a reload (read-only unless
--apply):

    uv run python -m educelab.hercdb.loader.extra_scan_links            # check only
    uv run python -m educelab.hercdb.loader.extra_scan_links --apply

Queries go to the driver directly, so a failed query raises instead of reading
as no rows.
"""
import argparse
import csv

DEFAULT_PATH = 'input_data/extra_scan_links.csv'
RAW_LABELS = ('PGSRaw', 'SpectralRaw')

# One row per listed link: whether the scan and the tray exist, and whether the
# edge is there. An excluded test scan is never re-linked.
CHECK_QUERY = """
    UNWIND $links AS l
    OPTIONAL MATCH (d {uuid: l.scan_uuid}) WHERE l.label IN labels(d)
    OPTIONAL MATCH (e:EduceLabID {uuid: l.eid})
    RETURN l.scan_uuid AS scan_uuid, l.eid AS eid,
           d IS NOT NULL AS scan_found, e IS NOT NULL AS tray_found,
           coalesce(d.excluded, false) AS excluded,
           EXISTS { (d)-[:BELONGS_TO]->(e) } AS linked
"""

LINK_QUERY = """
    UNWIND $links AS l
    MATCH (d {uuid: l.scan_uuid}) WHERE l.label IN labels(d) AND NOT coalesce(d.excluded, false)
    MATCH (e:EduceLabID {uuid: l.eid})
    MERGE (d)-[:BELONGS_TO]->(e)
    RETURN count(*) AS linked
"""


def load_links(path: str) -> list[dict]:
    """Read the CSV into ``$links`` rows. Raises ValueError on a label that
    isn't a raw scan type or a row missing a uuid."""
    links = []
    with open(path, newline='') as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            link = {k: (row.get(k) or '').strip() for k in ('label', 'scan_uuid', 'eid')}
            if link['label'] not in RAW_LABELS or not (link['scan_uuid'] and link['eid']):
                raise ValueError(f"{path} line {n}: need label in {RAW_LABELS}, scan_uuid and eid: {row}")
            links.append(link)
    return links


def check(driver, links) -> list[dict]:
    records, _, _ = driver.execute_query(CHECK_QUERY, links=links, database_='neo4j')
    return [r.data() for r in records]


def apply(driver, links) -> int:
    """MERGE every listed link; idempotent. Raises if a scan or tray is
    missing, so a typo in the list doesn't pass for "already linked"."""
    problems = [r for r in check(driver, links) if not (r['scan_found'] and r['tray_found'])]
    if problems:
        raise SystemExit(f"Extra scan links: scan or tray not found: {problems}")
    records, _, _ = driver.execute_query(LINK_QUERY, links=links, database_='neo4j')
    return records[0]['linked']


def main():
    from neo4j import GraphDatabase
    from educelab.hercdb import config

    parser = argparse.ArgumentParser(description="Apply the hand-kept extra scan links (#43).")
    parser.add_argument('--links', default=DEFAULT_PATH, help=f"CSV of links (default {DEFAULT_PATH}).")
    parser.add_argument('--apply', action='store_true', help="Create the missing links.")
    args = parser.parse_args()

    config.request_required()
    print(f"Target: {config.uri}")
    links = load_links(args.links)
    with GraphDatabase.driver(config.uri, auth=(config.username, config.password)) as driver:
        for r in check(driver, links):
            state = ('missing scan' if not r['scan_found'] else 'missing tray' if not r['tray_found']
                     else 'excluded scan' if r['excluded'] else 'linked' if r['linked'] else 'to link')
            print(f"  {r['scan_uuid']} -> {r['eid']}: {state}")
        if args.apply:
            print(f"Linked {apply(driver, links)} scan(s).")
        else:
            print("(check only -- re-run with --apply to write)")


if __name__ == '__main__':
    main()
