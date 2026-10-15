"""list_artifacts: every artifact with per-type dataset counts (#21).

Each row is checked against what the per-UUID reads already return:
identity against find_artifact_location_by_uuid, counts against
find_datasets_for_educelabid_with_predecessors (with the Python twin of the
completeness rule), catalogue against get_artifact_info of the PHerc.

Read-only. Requires a live Neo4j connection (dev, never prod).
"""
import random
import unittest

from educelab import hercdb
from educelab.hercdb.cli.scan_completeness import _is_fully_complete
from educelab.hercdb.db.connection import _PROCESSED_DATASET_LABELS, _as_datetime, _newer


def expected_counts(datasets):
    by_type = {}
    for d in datasets:
        entry = by_type.setdefault(d['type'], {'count': 0, 'complete': 0, 'failed': 0,
                                               'released': 0, 'newest': None})
        complete = _is_fully_complete(d)
        entry['count'] += 1
        entry['complete'] += complete
        entry['failed'] += d.get('status') == 'failed'
        entry['released'] += complete and d.get('released') is True
        if complete and d['type'] in _PROCESSED_DATASET_LABELS:
            ended = _as_datetime(d.get('date_end'))
            if entry['newest'] is None or _newer(ended, entry['newest'][0]):
                entry['newest'] = (ended, d['version'])
    for entry in by_type.values():
        newest = entry.pop('newest')
        entry['newest_complete_version'] = newest[1] if newest else None
    return by_type


class TestListArtifacts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        cls.rows = cls.db.list_artifacts()
        cls.by_uuid = {r['uuid']: r for r in cls.rows}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def _sample(self):
        """Random rows, plus one of each shape worth covering."""
        shared = [u for u, r in self.by_uuid.items() if len(r['artifacts']) > 1]
        failed = [u for u, r in self.by_uuid.items()
                  if any(t['failed'] for t in r['datasets'].values())]
        records, _, _ = self.db._run_query("""
            MATCH (e:EduceLabID)-[:ASSIGNED_TO]->() WHERE (e)-[:REPLACES]->()
            RETURN DISTINCT e.uuid AS uuid ORDER BY uuid LIMIT 1""")
        chained = [r['uuid'] for r in records or []]
        for name, found in (('shared', shared), ('failed', failed), ('chained', chained)):
            self.assertTrue(found, f"dev should have a {name} UUID to test")
        sample = set(random.Random(21).sample(sorted(self.by_uuid), 40))
        return sorted(sample | {shared[0], failed[0], chained[0]})

    def test_one_row_per_assigned_uuid(self):
        records, _, _ = self.db._run_query(
            "MATCH (e:EduceLabID)-[:ASSIGNED_TO]->() RETURN count(DISTINCT e) AS n")
        self.assertEqual(len(self.rows), records[0]['n'])
        self.assertEqual(len(self.by_uuid), len(self.rows))

    def test_rows_match_per_uuid_reads(self):
        for uuid in self._sample():
            row = self.by_uuid[uuid]
            with self.subTest(uuid=uuid, location=row['location']):
                location = self.db.find_artifact_location_by_uuid(uuid)
                location['location'] = self.db._format_dataset_name(location)
                self.assertEqual({k: row[k] for k in location}, location)
                self.assertEqual(row['artifacts'][0], location)

                datasets = self.db.find_datasets_for_educelabid_with_predecessors(uuid)
                self.assertEqual(row['datasets'], expected_counts(datasets))

                info = self.db.get_artifact_info(row['pherc'])
                if info is not None:  # None when two PHercs share the name
                    meta = info['metadata']
                    self.assertEqual(row['catalogue'], {
                        'author': meta.get('Author', {}).get('name'),
                        'work': info.get('literary_work'),
                        'language': meta.get('Language', {}).get('name'),
                    })

    def test_shared_uuid_lists_every_artifact(self):
        records, _, _ = self.db._run_query("""
            MATCH (e:EduceLabID)-[:ASSIGNED_TO]->(n)
            WITH e, count(n) AS n WHERE n > 1
            RETURN e.uuid AS uuid, n""")
        self.assertTrue(records)
        self.assertEqual({r['uuid']: r['n'] for r in records},
                         {u: len(r['artifacts']) for u, r in self.by_uuid.items()
                          if len(r['artifacts']) > 1})


if __name__ == "__main__":
    unittest.main()
