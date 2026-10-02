"""Integration tests for the dataset release flag and dataset UUIDs.

Requires a live Neo4j connection. Creates its own EduceLabID, scans and pipeline
under a TEST- prefix and removes them at the end, so it needs no existing data.
"""
import importlib.util
import json
import os
import tempfile
import unittest
import uuid as uuid_lib
from datetime import datetime

from educelab import hercdb
from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader

STAMP = datetime.now().strftime('%Y%m%d%H%M%S')
TEST_UUID = f"TEST-RELEASE-{STAMP}"
TEST_PIPELINE_ID = f"TEST-RELEASE-{STAMP}"
PGS_SCAN_UUID = str(uuid_lib.uuid4())
SPEC_SCAN_UUID = str(uuid_lib.uuid4())
# Already under the data root, so the loader stores them as given.
PGS_RAW = f"Dailies/test/release/pgs_raw/{STAMP}"
SPEC_RAW = f"Dailies/Spectral/test/release/spectral_raw/{STAMP}"
PGS_OUT = f"/test/release/pgs_processed/{STAMP}"
SPEC_OUT = f"/test/release/spectral_processed/{STAMP}"
PGS_OUT_UUID = str(uuid_lib.uuid4())
NOW = datetime.now().isoformat()


def _released(datasets, path):
    return next(d.get("released") for d in datasets if d["path"] == path)


class TestDatasetRelease(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        cls.loader = PhercGraphDatabaseLoader()
        cls.db._run_query("MERGE (:EduceLabID {uuid: $uuid})", uuid=TEST_UUID)

        # Raw scans take the config default (true unless configured otherwise).
        os.environ.pop("HERCDB_RELEASE_DEFAULT", None)
        cls.loader.add_pgs_raw_node(PGS_RAW, PGS_SCAN_UUID, NOW, NOW, complete="True",
                                    sample_uuid=TEST_UUID, file_count=1, missing_files=0,
                                    zero_byte_files=0, short_files=0, bad_format_files=0)
        cls.loader.add_spectral_raw_node(SPEC_RAW, SPEC_SCAN_UUID, NOW, NOW, complete="True",
                                         sample_uuid=TEST_UUID, file_count=1, missing_files=0,
                                         zero_byte_files=0, short_files=0, bad_format_files=0)

        cls.db.initialize_pipeline(TEST_PIPELINE_ID, TEST_UUID, NOW)
        cls.db.initialize_process(TEST_PIPELINE_ID, "PGS", [PGS_RAW], PGS_OUT, "1", NOW,
                                  output_dataset_uuid=PGS_OUT_UUID)
        cls.db.initialize_process(TEST_PIPELINE_ID, "SPEC", [SPEC_RAW], SPEC_OUT, "2", NOW,
                                  released=False)

    @classmethod
    def tearDownClass(cls):
        cls.db.delete_pipeline(TEST_PIPELINE_ID)
        cls.db._run_query("""
            MATCH (n) WHERE n.uuid IN $uuids OR n.path IN $paths
            DETACH DELETE n
        """, uuids=[TEST_UUID, PGS_SCAN_UUID, SPEC_SCAN_UUID],
            paths=[PGS_RAW, SPEC_RAW, PGS_OUT, SPEC_OUT])
        os.environ.pop("HERCDB_RELEASE_DEFAULT", None)
        cls.loader.close()
        cls.db.close()

    def datasets(self, **kwargs):
        return self.db.find_datasets_for_educelabid_with_predecessors(TEST_UUID, **kwargs)

    def test_1_defaults_on_create(self):
        datasets = self.datasets()
        self.assertIs(_released(datasets, PGS_RAW), True)
        self.assertIs(_released(datasets, SPEC_RAW), True)
        self.assertIs(_released(datasets, PGS_OUT), True)
        self.assertIs(_released(datasets, SPEC_OUT), False)

    def test_2_released_only_filter(self):
        paths = {d["path"] for d in self.datasets(released_only=True)}
        self.assertEqual(paths, {PGS_RAW, SPEC_RAW, PGS_OUT})

    def test_3_set_released_by_dataset_uuid(self):
        result = self.db.set_dataset_released(PGS_SCAN_UUID, False, "reviewer-a")
        self.assertEqual(result["matched"], 1)
        dataset = result["datasets"][0]
        self.assertEqual((dataset["type"], dataset["path"]), ("PGSRaw", PGS_RAW))
        self.assertIs(dataset["released"], False)
        self.assertEqual(dataset["released_by"], "reviewer-a")
        self.assertTrue(dataset["released_at"])
        self.assertIs(_released(self.datasets(), PGS_RAW), False)

        result = self.db.set_dataset_released(PGS_OUT_UUID, False, "reviewer-a")
        self.assertEqual(result["datasets"][0]["path"], PGS_OUT)
        self.db.set_dataset_released(PGS_OUT_UUID, True, "reviewer-a")
        self.assertIs(_released(self.datasets(), PGS_OUT), True)

    def test_4_output_uuid_recorded_and_read_back(self):
        out = next(d for d in self.datasets() if d["path"] == PGS_OUT)
        self.assertEqual(out["uuid"], PGS_OUT_UUID)
        # The SPEC output was recorded without one, so it waits for the backfill.
        self.assertNotIn("uuid", next(d for d in self.datasets() if d["path"] == SPEC_OUT))

    def test_4b_only_one_dataset_per_uuid(self):
        self.assertEqual(self.db.set_dataset_released("no-such-uuid", True, "x")["matched"], 0)
        # An EduceLabID has a `uuid` too, but isn't a dataset.
        self.assertEqual(self.db.set_dataset_released(TEST_UUID, True, "x")["matched"], 0)
        dup = f"/test/release/dup/{STAMP}"
        self.db._run_query("CREATE (:Registered {path: $p, uuid: $u, released: true})", p=dup, u=PGS_SCAN_UUID)
        try:
            result = self.db.set_dataset_released(PGS_SCAN_UUID, True, "x")
            self.assertEqual(result["matched"], 2)
            self.assertIs(_released(self.datasets(), PGS_RAW), False)  # untouched
        finally:
            self.db._run_query("MATCH (n {path: $p}) DETACH DELETE n", p=dup)

    def test_5_reload_keeps_flag(self):
        # Re-adding an existing scan (a --no-replace load) leaves its flag alone.
        self.loader.add_pgs_raw_node(PGS_RAW, PGS_SCAN_UUID, NOW, NOW, complete="True",
                                     sample_uuid=TEST_UUID, released=True)
        self.assertIs(_released(self.datasets(), PGS_RAW), False)

        # A --replace load deletes the node; the saved state puts the flag back.
        saved = [s for s in self.loader.get_scan_release_states() if s["uuid"] == PGS_SCAN_UUID]
        self.assertEqual(len(saved), 1)
        self.db._run_query("MATCH (n:PGSRaw {uuid: $u}) DETACH DELETE n", u=PGS_SCAN_UUID)
        self.loader.add_pgs_raw_node(PGS_RAW, PGS_SCAN_UUID, NOW, NOW, complete="True",
                                     sample_uuid=TEST_UUID)
        self.assertIs(_released(self.datasets(), PGS_RAW), True)
        self.loader.restore_scan_release_states(saved)
        datasets = self.datasets()
        self.assertIs(_released(datasets, PGS_RAW), False)
        self.assertEqual(next(d for d in datasets if d["path"] == PGS_RAW)["released_by"], "reviewer-a")

    def test_6_configured_default(self):
        # A scan created while the default is false starts out unreleased.
        os.environ["HERCDB_RELEASE_DEFAULT"] = "false"
        try:
            self.db._run_query("MATCH (n:SpectralRaw {uuid: $u}) DETACH DELETE n", u=SPEC_SCAN_UUID)
            self.loader.add_spectral_raw_node(SPEC_RAW, SPEC_SCAN_UUID, NOW, NOW, complete="True",
                                              sample_uuid=TEST_UUID)
            self.assertIs(_released(self.datasets(), SPEC_RAW), False)
        finally:
            os.environ.pop("HERCDB_RELEASE_DEFAULT", None)

    def test_7_uuid_migration_reads_metadata(self):
        spec = importlib.util.spec_from_file_location(
            "migrate_dataset_uuids",
            os.path.join(os.path.dirname(__file__), "..", "..", "preprocessing", "migrate_dataset_uuids.py"))
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        on_disk = str(uuid_lib.uuid4())
        with tempfile.TemporaryDirectory() as root:
            out_dir = os.path.join(root, SPEC_OUT.strip("/"))
            os.makedirs(out_dir)
            with open(os.path.join(out_dir, "metadata.json"), "w") as f:
                json.dump({"schema_version": "2.1", "dataset_type": "SpectralProcessed", "uuid": on_disk}, f)

            rows, taken = migration.fetch(self.db)
            self.assertIn(PGS_OUT_UUID, taken)
            rows = [r for r in rows if r["path"] == SPEC_OUT]
            planned = migration.plan(rows, taken, migration.Path(root))
            self.assertEqual((planned[0]["outcome"], planned[0]["uuid"]), (migration.FROM_METADATA, on_disk))
            migration.apply(self.db, planned, mint_missing=False)

        self.assertEqual(next(d for d in self.datasets() if d["path"] == SPEC_OUT)["uuid"], on_disk)
        self.assertEqual(migration.read_uuid(migration.Path("/nonexistent"), "x"), (migration.NO_FILE, None))


if __name__ == "__main__":
    unittest.main()
