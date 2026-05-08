"""Integration tests for pipeline CRUD methods on GraphDBConnection.

Requires a live Neo4j connection. These tests create temporary pipeline/process
nodes and clean them up at the end.
"""
import unittest
from datetime import datetime

from educelab import hercdb


# Test constants — use a known EduceLabID UUID that exists in the DB
TEST_ARTIFACT_UUID = "d65a2db0-ffec-5c15-8d3e-b28cf9326a32"
TEST_PIPELINE_ID = f"TEST-CRUD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
TEST_DATETIME = datetime.now().isoformat()

# Fake paths for test dataset nodes
PGS_RAW_INPUT = "/test/pgs_raw/input"
SPEC_RAW_INPUT = "/test/spectral_raw/input"
PGS_PROCESSED_OUTPUT = f"/test/pgs_processed/{TEST_PIPELINE_ID}"
SPEC_PROCESSED_OUTPUT = f"/test/spectral_processed/{TEST_PIPELINE_ID}"
REGISTERED_OUTPUT = f"/test/registered/{TEST_PIPELINE_ID}"
WEB_OUTPUT = f"/test/web_processed/{TEST_PIPELINE_ID}"


class TestPipelineCrud(unittest.TestCase):
    """Tests that run in order: create pipeline → add processes → update → confirm."""

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()

        # Verify the test artifact UUID exists
        artifact = cls.db.find_artifact_name_by_uuid(TEST_ARTIFACT_UUID)
        assert artifact is not None, (
            f"Test artifact UUID {TEST_ARTIFACT_UUID} not found in DB. "
            "Update TEST_ARTIFACT_UUID to a valid EduceLabID."
        )
        print(f"\nUsing artifact: {artifact} (UUID: {TEST_ARTIFACT_UUID})")
        print(f"Test pipeline ID: {TEST_PIPELINE_ID}")

        # We also need PGSRaw and SpectralRaw datasets linked to this UUID.
        # Create temporary ones for the test.
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            MERGE (pgs:PGSRaw {path: $pgs_path})
            MERGE (spec:SpectralRaw {path: $spec_path})
            MERGE (pgs)-[:BELONGS_TO]->(e)
            MERGE (spec)-[:BELONGS_TO]->(e)
            """, uuid=TEST_ARTIFACT_UUID, pgs_path=PGS_RAW_INPUT, spec_path=SPEC_RAW_INPUT)

    @classmethod
    def tearDownClass(cls):
        """Remove all test nodes created during the tests."""
        # Delete the pipeline and all connected process/output nodes
        cls.db._run_query("""
            MATCH (p:Pipeline {pipeline_id: $pipeline_id})
            OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
            OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
            OPTIONAL MATCH (inp)-[:INPUT]->(proc)
            DETACH DELETE proc, out, p
            """, pipeline_id=TEST_PIPELINE_ID)

        # Delete the temporary raw input datasets
        cls.db._run_query("""
            MATCH (n {path: $pgs_path}) DETACH DELETE n
            """, pgs_path=PGS_RAW_INPUT)
        cls.db._run_query("""
            MATCH (n {path: $spec_path}) DETACH DELETE n
            """, spec_path=SPEC_RAW_INPUT)

        # Delete any output nodes by path
        for path in [PGS_PROCESSED_OUTPUT, SPEC_PROCESSED_OUTPUT, REGISTERED_OUTPUT, WEB_OUTPUT]:
            cls.db._run_query("MATCH (n {path: $path}) DETACH DELETE n", path=path)

        print(f"\nCleaned up test pipeline: {TEST_PIPELINE_ID}")
        cls.db.close()

    def test_1_initialize_pipeline(self):
        result = self.db.initialize_pipeline(TEST_PIPELINE_ID, TEST_ARTIFACT_UUID, TEST_DATETIME)
        self.assertIsNotNone(result)
        self.assertEqual(result['pipeline_id'], TEST_PIPELINE_ID)
        self.assertEqual(result['artifact_uuid'], TEST_ARTIFACT_UUID)
        self.assertEqual(result['datetime'], TEST_DATETIME)
        print(f"[initialize_pipeline] {result}")

    def test_2_initialize_pipeline_bad_uuid(self):
        result = self.db.initialize_pipeline("SHOULD-NOT-EXIST", "nonexistent-uuid", TEST_DATETIME)
        self.assertIsNone(result)
        print("[initialize_pipeline bad uuid] Correctly returned None")

    def test_3_initialize_pgs_process(self):
        result = self.db.initialize_process(
            pipeline_id=TEST_PIPELINE_ID,
            proc_type="PGS",
            input_dataset_paths=[PGS_RAW_INPUT],
            output_dataset_path=PGS_PROCESSED_OUTPUT,
            slurm_id="12345",
            start_datetime=TEST_DATETIME,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['stage'], 'PGS')
        self.assertEqual(result['status'], 'submitted')
        self.assertEqual(result['slurm_id'], '12345')
        print(f"[initialize_process PGS] {result}")

    def test_4_initialize_spec_process(self):
        result = self.db.initialize_process(
            pipeline_id=TEST_PIPELINE_ID,
            proc_type="SPEC",
            input_dataset_paths=[SPEC_RAW_INPUT],
            output_dataset_path=SPEC_PROCESSED_OUTPUT,
            slurm_id="12346",
            start_datetime=TEST_DATETIME,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['stage'], 'SPEC')
        self.assertEqual(result['status'], 'submitted')
        print(f"[initialize_process SPEC] {result}")

    def test_5_update_pgs_completed(self):
        end_dt = datetime.now().isoformat()
        result = self.db.update_process_status(TEST_PIPELINE_ID, "PGS", "completed", end_dt)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], 'completed')
        self.assertIsNotNone(result['end_time'])
        print(f"[update_process_status PGS completed] {result}")

    def test_6_update_spec_completed(self):
        end_dt = datetime.now().isoformat()
        result = self.db.update_process_status(TEST_PIPELINE_ID, "SPEC", "completed", end_dt)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], 'completed')
        print(f"[update_process_status SPEC completed] {result}")

    def test_7_initialize_reg_process(self):
        result = self.db.initialize_process(
            pipeline_id=TEST_PIPELINE_ID,
            proc_type="REG",
            input_dataset_paths=[PGS_PROCESSED_OUTPUT, SPEC_PROCESSED_OUTPUT],
            output_dataset_path=REGISTERED_OUTPUT,
            slurm_id="12347",
            start_datetime=TEST_DATETIME,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['stage'], 'REG')
        self.assertEqual(result['status'], 'submitted')
        print(f"[initialize_process REG] {result}")

    def test_8_update_reg_failed(self):
        end_dt = datetime.now().isoformat()
        result = self.db.update_process_status(TEST_PIPELINE_ID, "REG", "failed", end_dt)
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNotNone(result['end_time'])
        print(f"[update_process_status REG failed] {result}")

    def test_9_get_pipeline_confirmation(self):
        result = self.db.get_pipeline_confirmation(TEST_PIPELINE_ID)
        self.assertIsNotNone(result)
        self.assertEqual(result['pipeline_id'], TEST_PIPELINE_ID)
        self.assertEqual(result['artifact_uuid'], TEST_ARTIFACT_UUID)
        self.assertEqual(result['datetime'], TEST_DATETIME)
        self.assertIn(result['status'], ['partially_completed', 'completed', 'failed', 'running', 'unknown(error)'])
        self.assertIsInstance(result['stages'], list)
        self.assertTrue(len(result['stages']) >= 3)

        stage_types = [s['proc_type'] for s in result['stages']]
        self.assertIn('PGS', stage_types)
        self.assertIn('SPEC', stage_types)
        self.assertIn('REG', stage_types)

        print(f"[get_pipeline_confirmation] status={result['status']}, stages={len(result['stages'])}")
        for s in result['stages']:
            print(f"  {s['proc_type']}: {s['status']} (slurm: {s['slurm_id']})")

    def test_9b_get_pipeline_confirmation_not_found(self):
        result = self.db.get_pipeline_confirmation("nonexistent-pipeline")
        self.assertIsNone(result)
        print("[get_pipeline_confirmation not found] Correctly returned None")


if __name__ == "__main__":
    unittest.main()
