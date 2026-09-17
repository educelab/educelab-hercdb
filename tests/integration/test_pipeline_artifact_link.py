"""Integration tests for the Pipeline -> artifact link used by the pipeline list.

Regression cover for a REG/WEB pipeline losing its artifact. `find_pipelines`
used to reconstruct the link by walking to a *raw* input
(`(PGSRaw|SpectralRaw)-[:BELONGS_TO]->(EduceLabID)`), which matches nothing for a
pipeline whose inputs are processed datasets. `get_all_pipeline_summaries` then
reported such a pipeline with an empty `artifact_uuid` -- and an empty
`dataset_name` too, because the name lookup is gated on the uuid -- so the UI's
pipeline list showed two blank columns.

The fixture mirrors a real registration-only submission: one pipeline produces
PGSProcessed and SpectralProcessed from raw scans, then a *separate* pipeline
runs REG over those outputs, exactly as `submit_registration_pipeline.py` does.

Requires a live Neo4j connection. All nodes created here are removed in
tearDownClass.
"""
import os
import unittest
from datetime import datetime

from educelab import hercdb


# A known EduceLabID that exists in the DB, as the other integration tests do.
TEST_ARTIFACT_UUID = "d65a2db0-ffec-5c15-8d3e-b28cf9326a32"

_STAMP = datetime.now().strftime("%Y%m%d%H%M%S")
SOURCE_PIPELINE_ID = f"TEST-LINK-SRC-{_STAMP}"
REG_PIPELINE_ID = f"TEST-LINK-REG-{_STAMP}"
TEST_DATETIME = datetime.now().isoformat()

PGS_RAW = f"/test/link/{_STAMP}/pgs_raw"
SPEC_RAW = f"/test/link/{_STAMP}/spectral_raw"
PGS_PROCESSED = f"/test/link/{_STAMP}/pgs_processed"
SPEC_PROCESSED = f"/test/link/{_STAMP}/spectral_processed"
REGISTERED = f"/test/link/{_STAMP}/registered"

ALL_TEST_PATHS = [PGS_RAW, SPEC_RAW, PGS_PROCESSED, SPEC_PROCESSED, REGISTERED]


class TestPipelineArtifactLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()

        artifact = cls.db.find_artifact_name_by_uuid(TEST_ARTIFACT_UUID)
        assert artifact is not None, (
            f"Test artifact UUID {TEST_ARTIFACT_UUID} not found in DB. "
            "Update TEST_ARTIFACT_UUID to a valid EduceLabID."
        )
        cls.artifact_name = cls.db._format_dataset_name(artifact)
        print(f"\nUsing artifact: {cls.artifact_name} (UUID: {TEST_ARTIFACT_UUID})")

        # Raw scans for the source pipeline to consume.
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            MERGE (pgs:PGSRaw {path: $pgs_path})
            MERGE (spec:SpectralRaw {path: $spec_path})
            MERGE (pgs)-[:BELONGS_TO]->(e)
            MERGE (spec)-[:BELONGS_TO]->(e)
            """, uuid=TEST_ARTIFACT_UUID, pgs_path=PGS_RAW, spec_path=SPEC_RAW)

        # Source pipeline: raw -> PGSProcessed / SpectralProcessed.
        cls.db.initialize_pipeline(SOURCE_PIPELINE_ID, TEST_ARTIFACT_UUID, TEST_DATETIME)
        cls.db.initialize_process(
            SOURCE_PIPELINE_ID, "PGS", [PGS_RAW], PGS_PROCESSED, "1", TEST_DATETIME)
        cls.db.initialize_process(
            SOURCE_PIPELINE_ID, "SPEC", [SPEC_RAW], SPEC_PROCESSED, "2", TEST_DATETIME)

        # Registration-only pipeline over those outputs -- no raw input of its own.
        cls.db.initialize_pipeline(REG_PIPELINE_ID, TEST_ARTIFACT_UUID, TEST_DATETIME)
        cls.reg_process = cls.db.initialize_process(
            REG_PIPELINE_ID, "REG", [PGS_PROCESSED, SPEC_PROCESSED],
            REGISTERED, "3", TEST_DATETIME)
        assert cls.reg_process is not None, (
            "initialize_process returned None for the REG stage -- the fixture "
            "never got built, so the assertions below would be meaningless."
        )

    @classmethod
    def tearDownClass(cls):
        for pipeline_id in (SOURCE_PIPELINE_ID, REG_PIPELINE_ID):
            cls.db._run_query("""
                MATCH (p:Pipeline {pipeline_id: $pipeline_id})
                OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
                DETACH DELETE proc, p
                """, pipeline_id=pipeline_id)
        for path in ALL_TEST_PATHS:
            cls.db._run_query("MATCH (n {path: $path}) DETACH DELETE n", path=path)
        print(f"\nCleaned up test pipelines: {SOURCE_PIPELINE_ID}, {REG_PIPELINE_ID}")
        cls.db.close()

    def test_reg_only_pipeline_resolves_its_artifact(self):
        """The regression: a REG pipeline has no raw input, but it has a FOR edge."""
        links = {p["pipeline_id"]: p["artifact_uuid"] for p in self.db.find_pipelines()}
        self.assertIn(
            REG_PIPELINE_ID, links,
            "find_pipelines dropped a registration-only pipeline -- it is probably "
            "matching on a raw input again rather than following [:FOR].")
        self.assertEqual(links[REG_PIPELINE_ID], TEST_ARTIFACT_UUID)

    def test_raw_input_pipeline_still_resolves(self):
        """PGS/SPEC pipelines must keep working -- they were never broken."""
        links = {p["pipeline_id"]: p["artifact_uuid"] for p in self.db.find_pipelines()}
        self.assertIn(SOURCE_PIPELINE_ID, links)
        self.assertEqual(links[SOURCE_PIPELINE_ID], TEST_ARTIFACT_UUID)

    def test_find_pipelines_returns_one_row_per_pipeline(self):
        """Two raw inputs on one pipeline must not become two rows."""
        ids = [p["pipeline_id"] for p in self.db.find_pipelines()]
        self.assertEqual(ids.count(SOURCE_PIPELINE_ID), 1)
        self.assertEqual(ids.count(REG_PIPELINE_ID), 1)

    def test_both_summary_columns_resolve(self):
        """The two columns the UI renders, without the whole-database walk.

        `get_all_pipeline_summaries` composes exactly these two steps: it looks
        the pipeline up in `find_pipelines`, then gates the name lookup on the
        uuid that came back (`if artifact_uuid:`). Both blank columns in the bug
        came from the first step returning nothing, so asserting the pair here
        covers the whole causal chain.

        Calling the real function instead would issue one `get_pipeline_status`
        query per pipeline in the database -- 3600+ round trips, minutes over a
        VPN -- to check a single row. `test_summary_row_carries_uuid_and_name`
        below does that, opt-in.
        """
        links = {p["pipeline_id"]: p["artifact_uuid"] for p in self.db.find_pipelines()}
        artifact_uuid = links.get(REG_PIPELINE_ID)
        self.assertTrue(
            artifact_uuid,
            "no artifact_uuid for the REG pipeline -- dataset_name is gated on it, "
            "so the pipeline list would show two blank columns.")

        artifact = self.db.find_artifact_name_by_uuid(artifact_uuid)
        self.assertIsNotNone(artifact, f"uuid {artifact_uuid} resolved to no artifact")
        self.assertEqual(self.db._format_dataset_name(artifact), self.artifact_name)

    @unittest.skipUnless(
        os.environ.get("HERCDB_SLOW_TESTS"),
        "walks every pipeline in the database; set HERCDB_SLOW_TESTS=1 to run")
    def test_summary_row_carries_uuid_and_name(self):
        """The same assertion through the real function callers use.

        Worth running on a host near the database, where the N+1 is seconds
        rather than minutes.
        """
        summaries = {s["pipeline_id"]: s for s in self.db.get_all_pipeline_summaries()}
        self.assertIn(REG_PIPELINE_ID, summaries)
        row = summaries[REG_PIPELINE_ID]
        self.assertEqual(row["artifact_uuid"], TEST_ARTIFACT_UUID)
        self.assertEqual(row["dataset_name"], self.artifact_name)
        print(f"[summary] {row}")


if __name__ == "__main__":
    unittest.main()
