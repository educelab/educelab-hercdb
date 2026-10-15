"""Retried and resubmitted pipeline stages (#12).

- Recording a submission again must not add a second Process, even after its
  status has moved on (the Process MERGE key used to include ``status``).
- A processed dataset with several Processes OUTPUT-ing to it comes back as one
  row, from its newest Process.
- A pipeline resubmitted under the same pipeline_id holds one Process per
  attempt; a status update must change only the newest.

Requires a live Neo4j connection (dev, never prod). Seeds its own nodes under a
real EduceLabID and removes them afterwards.
"""
import unittest
from datetime import datetime

from educelab import hercdb
from educelab.hercdb.loader import PhercGraphDatabaseLoader

_TS = datetime.now().strftime('%Y%m%d%H%M%S')
PHERC = "1044"


class TestProcessRetries(unittest.TestCase):

    PID = f"TEST-RETRY-{_TS}"
    OTHER_PID = f"TEST-RETRY-OTHER-{_TS}"
    LOADER_PID = f"TEST-RETRY-LOADER-{_TS}"
    RAW = f"/test/retry/pgs_raw/{_TS}"
    OUT = f"/test/retry/pgs_processed/{_TS}"
    LOADER_OUT = f"/test/retry/pgs_processed_loader/{_TS}"
    SHARED_OUT = f"/test/retry/shared_output/{_TS}"
    ATTEMPTS_PID = f"TEST-RETRY-ATTEMPTS-{_TS}"

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        cls.loader = PhercGraphDatabaseLoader()
        artifacts = cls.db.find_all_datasets_for_pherc(PHERC)
        assert artifacts, f"Need at least one UUID under {PHERC} to test"
        cls.uuid = artifacts[0]['uuid']

        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            CREATE (:PGSRaw {path: $raw, uuid: $raw})-[:BELONGS_TO]->(e)
            """, uuid=cls.uuid, raw=cls.RAW)
        for pid in (cls.PID, cls.OTHER_PID):
            cls.db.initialize_pipeline(pid, cls.uuid, '2026-10-01T00:00:00')

        # One output written by two Processes of one pipeline: an earlier
        # attempt that failed and a later one that completed.
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            CREATE (p:Pipeline {pipeline_id: $pid})-[:FOR]->(e)
            CREATE (out:PGSProcessed {path: $out})
            CREATE (:Process {stage: 'PGS', status: 'failed', slurm_id: '1',
                              start_time: '2026-10-01T10:00:00',
                              end_time: '2026-10-01T10:05:00'})-[:STAGE_OF]->(p)
            CREATE (:Process {stage: 'PGS', status: 'completed', slurm_id: '2',
                              start_time: '2026-10-02T10:00:00',
                              end_time: '2026-10-02T11:00:00'})-[:STAGE_OF]->(p)
            WITH p, out
            MATCH (p)<-[:STAGE_OF]-(proc:Process)
            CREATE (proc)-[:OUTPUT]->(out)
            """, uuid=cls.uuid, pid=cls.ATTEMPTS_PID, out=cls.SHARED_OUT)

    @classmethod
    def tearDownClass(cls):
        for pid in (cls.PID, cls.OTHER_PID, cls.LOADER_PID, cls.ATTEMPTS_PID):
            cls.db._run_query("""
                MATCH (p:Pipeline {pipeline_id: $pid})
                OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
                OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
                DETACH DELETE out, proc, p
                """, pid=pid)
        cls.db._run_query("MATCH (n {path: $raw}) DETACH DELETE n", raw=cls.RAW)
        cls.loader.close()
        cls.db.close()

    def _processes(self, pid, stage='PGS'):
        records, _, _ = self.db._run_query("""
            MATCH (:Pipeline {pipeline_id: $pid})<-[:STAGE_OF]-(proc:Process {stage: $stage})
            RETURN proc.slurm_id AS slurm_id, proc.status AS status
            ORDER BY proc.start_time
            """, pid=pid, stage=stage)
        return [dict(r) for r in records or []]

    def _record(self, pid, start='2026-10-03T09:00:00', slurm='77', out=None):
        return self.db.initialize_process(pid, 'PGS', [self.RAW], out or self.OUT, slurm, start)

    # -- A: recording is idempotent -------------------------------------------

    def test_a_rerecording_after_status_update_keeps_one_process(self):
        self.assertEqual(self._record(self.PID)['status'], 'submitted')
        self.db.update_process_status(self.PID, 'PGS', 'completed', '2026-10-03T10:00:00')
        again = self._record(self.PID)
        self.assertEqual(again['status'], 'completed', "re-recording must not reset status")
        self.assertEqual(self._processes(self.PID), [{'slurm_id': '77', 'status': 'completed'}])

    def test_a_same_job_keys_in_two_pipelines_are_two_processes(self):
        out = f"{self.OUT}-other"
        self._record(self.PID, start='2026-10-04T09:00:00', slurm='88', out=out)
        self._record(self.OTHER_PID, start='2026-10-04T09:00:00', slurm='88', out=out)
        # One node with two STAGE_OF edges would look like one Process to each
        # pipeline, so count the distinct nodes.
        records, _, _ = self.db._run_query("""
            MATCH (pl:Pipeline)<-[:STAGE_OF]-(proc:Process {slurm_id: '88'})
            WHERE pl.pipeline_id IN $pids
            RETURN count(DISTINCT proc) AS procs, count(*) AS edges
            """, pids=[self.PID, self.OTHER_PID])
        self.assertEqual(dict(records[0]), {'procs': 2, 'edges': 2})

    def test_a_loader_rerecording_keeps_one_process(self):
        args = (self.uuid, 'PGS', self.RAW, self.LOADER_OUT, '2026-10-05T09:00:00', '99', self.LOADER_PID)
        self.loader.add_image_processing_node(*args)
        self.loader.update_process_status(self.LOADER_PID, 'PGS', 'status', 'completed')
        self.loader.add_image_processing_node(*args)
        self.assertEqual(self._processes(self.LOADER_PID), [{'slurm_id': '99', 'status': 'completed'}])

    # -- B: one row per processed dataset -------------------------------------

    def _shared_rows(self, datasets):
        return [d for d in datasets if d.get('path') == self.SHARED_OUT]

    def test_b_dataset_reads_return_one_row_from_newest_process(self):
        reads = {
            'with_predecessors': self.db.find_datasets_for_educelabid_with_predecessors(self.uuid),
            'single_uuid': self.db.find_datasets_for_educelabid(self.uuid),
            'all_for_pherc': [d for a in self.db.find_all_datasets_for_pherc(PHERC)
                              if a['uuid'] == self.uuid for d in a['datasets']],
        }
        for name, datasets in reads.items():
            with self.subTest(read=name):
                rows = self._shared_rows(datasets)
                self.assertEqual(len(rows), 1, f"{name}: expected one row for the shared output")
                self.assertEqual(rows[0]['status'], 'completed')
                self.assertEqual(rows[0]['complete'], 'True')
                self.assertEqual(rows[0]['date_end'], '2026-10-02T11:00:00')

    def test_b_newest_completed_keeps_the_output(self):
        datasets = self.db.find_datasets_for_educelabid_with_predecessors(
            self.uuid, ds_type=hercdb.DatasetType.PGSProcessed, newest_completed=True)
        self.assertTrue(datasets)

    # -- C: status updates hit the newest attempt -----------------------------

    def test_c_status_update_changes_only_newest_attempt(self):
        pid = f"{self.ATTEMPTS_PID}-C"
        self.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            CREATE (p:Pipeline {pipeline_id: $pid})-[:FOR]->(e)
            CREATE (:Process {stage: 'PGS', status: 'failed', slurm_id: 'old',
                              start_time: '2026-10-01T10:00:00'})-[:STAGE_OF]->(p)
            CREATE (:Process {stage: 'PGS', status: 'submitted', slurm_id: 'new',
                              start_time: '2026-10-02T10:00:00'})-[:STAGE_OF]->(p)
            """, uuid=self.uuid, pid=pid)
        self.addCleanup(self.db._run_query, """
            MATCH (p:Pipeline {pipeline_id: $pid}) OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc)
            DETACH DELETE proc, p""", pid=pid)

        result = self.db.update_process_status(pid, 'PGS', 'completed', '2026-10-02T11:00:00')
        self.assertEqual(result['slurm_id'], 'new')
        self.assertEqual(self._processes(pid), [{'slurm_id': 'old', 'status': 'failed'},
                                                {'slurm_id': 'new', 'status': 'completed'}])

        self.loader.update_process_status(pid, 'PGS', 'status', 'archiving')
        self.assertEqual(self._processes(pid), [{'slurm_id': 'old', 'status': 'failed'},
                                                {'slurm_id': 'new', 'status': 'archiving'}])


if __name__ == "__main__":
    unittest.main()
