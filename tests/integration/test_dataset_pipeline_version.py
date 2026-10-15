"""Processed datasets carry the version of the pipeline that produced them (#27).

Every dataset read returns ``version`` beside ``pipeline_id`` on a processed
row -- ``None`` when the Pipeline recorded none -- and never adds it to a raw
scan.

Requires a live Neo4j connection (dev, never prod). Seeds its own nodes under a
real EduceLabID and removes them afterwards.
"""
import unittest
from datetime import datetime

from educelab import hercdb

_TS = datetime.now().strftime('%Y%m%d%H%M%S')
PHERC = "1044"


class TestDatasetPipelineVersion(unittest.TestCase):

    VERSIONED_PID = f"TEST-VERSION-{_TS}"
    UNVERSIONED_PID = f"TEST-VERSION-NONE-{_TS}"
    RAW = f"/test/version/pgs_raw/{_TS}"
    VERSIONED_OUT = f"/test/version/pgs_processed/{_TS}"
    UNVERSIONED_OUT = f"/test/version/pgs_processed_none/{_TS}"

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        artifacts = cls.db.find_all_datasets_for_pherc(PHERC)
        assert artifacts, f"Need at least one UUID under {PHERC} to test"
        cls.uuid = artifacts[0]['uuid']

        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            CREATE (:PGSRaw {path: $raw, uuid: $raw})-[:BELONGS_TO]->(e)
            """, uuid=cls.uuid, raw=cls.RAW)
        # Far-future end times, so newest_completed picks these over real data.
        runs = ((cls.VERSIONED_PID, '2.1.0', cls.VERSIONED_OUT, '2099-01-02T00:00:00'),
                (cls.UNVERSIONED_PID, None, cls.UNVERSIONED_OUT, '2099-01-01T00:00:00'))
        for pid, version, out, end in runs:
            cls.db.initialize_pipeline(pid, cls.uuid, '2099-01-01T00:00:00', version=version)
            cls.db.initialize_process(pid, 'PGS', [cls.RAW], out, '1', '2099-01-01T00:00:00')
            cls.db.update_process_status(pid, 'PGS', 'completed', end)

    @classmethod
    def tearDownClass(cls):
        for pid in (cls.VERSIONED_PID, cls.UNVERSIONED_PID):
            cls.db._run_query("""
                MATCH (p:Pipeline {pipeline_id: $pid})
                OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
                OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
                DETACH DELETE out, proc, p
                """, pid=pid)
        cls.db._run_query("MATCH (n {path: $raw}) DETACH DELETE n", raw=cls.RAW)
        cls.db.close()

    def _reads(self, **kwargs):
        return {
            'with_predecessors': self.db.find_datasets_for_educelabid_with_predecessors(self.uuid, **kwargs),
            'single_uuid': self.db.find_datasets_for_educelabid(self.uuid, **kwargs),
            'all_for_pherc': [d for a in self.db.find_all_datasets_for_pherc(PHERC, **kwargs)
                              if a['uuid'] == self.uuid for d in a['datasets']],
        }

    def test_processed_rows_carry_pipeline_version(self):
        for name, datasets in self._reads().items():
            with self.subTest(read=name):
                by_path = {d.get('path'): d for d in datasets}
                self.assertEqual(by_path[self.VERSIONED_OUT]['version'], '2.1.0')
                self.assertEqual(by_path[self.VERSIONED_OUT]['pipeline_id'], self.VERSIONED_PID)
                self.assertIn('version', by_path[self.UNVERSIONED_OUT])
                self.assertIsNone(by_path[self.UNVERSIONED_OUT]['version'])

    def test_raw_rows_have_no_version(self):
        for name, datasets in self._reads().items():
            with self.subTest(read=name):
                raw = next(d for d in datasets if d.get('path') == self.RAW)
                self.assertNotIn('version', raw)

    def test_newest_completed_keeps_version(self):
        for name, datasets in self._reads(ds_type=hercdb.DatasetType.PGSProcessed,
                                          newest_completed=True).items():
            with self.subTest(read=name):
                self.assertEqual([(d['path'], d['version']) for d in datasets],
                                 [(self.VERSIONED_OUT, '2.1.0')])


if __name__ == "__main__":
    unittest.main()
