import unittest
from datetime import datetime

from educelab import hercdb

# Self-seeded pipelines for the get_pipeline_status tests. Created in setUpClass
# and removed in tearDownClass so the tests don't depend on hand-curated reference
# data living in whatever DB we point at. IDs are timestamped to avoid collisions.
_TS = datetime.now().strftime('%Y%m%d%H%M%S')
STATUS_PIPELINE_ID = f"TEST-STATUS-{_TS}"
THREE_STAGE_PIPELINE_ID = f"TEST-3STAGE-{_TS}"

# A mixed-status pipeline (one completed stage, one still submitted).
_STATUS_PROCS = [
    {'stage': 'PGS', 'status': 'completed', 'slurm_id': '900001',
     'start_time': '2026-01-01T10:00:00', 'end_time': '2026-01-01T10:30:00'},
    {'stage': 'SPEC', 'status': 'submitted', 'slurm_id': '900002',
     'start_time': '2026-01-01T10:31:00', 'end_time': None},
]
# Exactly three completed stages: PGS, SPEC, REG (no WEB).
_THREE_STAGE_PROCS = [
    {'stage': 'PGS', 'status': 'completed', 'slurm_id': '900101',
     'start_time': '2026-02-03T09:00:00', 'end_time': '2026-02-03T09:45:00'},
    {'stage': 'SPEC', 'status': 'completed', 'slurm_id': '900102',
     'start_time': '2026-02-03T09:46:00', 'end_time': '2026-02-03T10:10:00'},
    {'stage': 'REG', 'status': 'completed', 'slurm_id': '900103',
     'start_time': '2026-02-03T10:11:00', 'end_time': '2026-02-03T10:40:00'},
]


class TestPhercDbQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.query_runner = hercdb.connect()
        cls.query_runner.verify_connection()
        cls._seed_pipeline(STATUS_PIPELINE_ID, _STATUS_PROCS)
        cls._seed_pipeline(THREE_STAGE_PIPELINE_ID, _THREE_STAGE_PROCS)

    @classmethod
    def _seed_pipeline(cls, pipeline_id, procs):
        cls.query_runner._run_query("""
            MERGE (p:Pipeline {pipeline_id: $pid})
            WITH p
            UNWIND $procs AS proc
            CREATE (pr:Process)
            SET pr += proc
            CREATE (pr)-[:STAGE_OF]->(p)
            """, pid=pipeline_id, procs=procs)

    @classmethod
    def tearDownClass(cls):
        for pid in (STATUS_PIPELINE_ID, THREE_STAGE_PIPELINE_ID):
            cls.query_runner._run_query("""
                MATCH (p:Pipeline {pipeline_id: $pid})
                OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
                DETACH DELETE proc, p
                """, pid=pid)

    def test_find_artifact_name_by_uuid(self):
        result = self.query_runner.find_artifact_name_by_uuid("d65a2db0-ffec-5c15-8d3e-b28cf9326a32")
        self.assertIsNotNone(result)
        self.assertIn('pherc', result)
        self.assertIsNotNone(result['pherc'])
        print(f"[find_artifact_name_by_uuid] Result: {result}")

    def _a_uuid_under_1044(self) -> str:
        """Pull one EduceLabID uuid under PHerc 1044 (datasets path)."""
        artifacts = self.query_runner.find_all_datasets_for_pherc("1044")
        self.assertTrue(len(artifacts) > 0, "Need at least one UUID under 1044 to test")
        return artifacts[0]['uuid']

    def test_get_artifact_info_pherc(self):
        info = self.query_runner.get_artifact_info("1044")
        self.assertIsNotNone(info)
        self.assertEqual(info['type'], 'PHerc')
        self.assertIn('displayName', info)
        self.assertIn('educelabids', info)
        self.assertIsInstance(info['educelabids'], list)
        self.assertIn('cornici_count', info)
        self.assertIn('pezzi_count', info)
        self.assertIn('metadata', info)
        print(f"[get_artifact_info '1044'] {info}")

    def test_get_artifact_info_not_found(self):
        self.assertIsNone(self.query_runner.get_artifact_info("nonexistent_pherc"))

    def test_list_cornici_and_pezzi_for_pherc(self):
        result = self.query_runner.list_cornici_and_pezzi_for_pherc("238")
        self.assertIsNotNone(result)
        self.assertIn('pherc', result)
        self.assertIn('cornici', result)
        self.assertIn('pezzi', result)
        # Every listed node carries the enriched shape, including its parent
        for node in result['cornici'] + result['pezzi']:
            self.assertIn('displayName', node)
            self.assertIn('aliases', node)
            self.assertIn('educelabids', node)
            self.assertIn('parent', node)
        # Cornici hang off the PHerc itself
        for cornice in result['cornici']:
            self.assertIsNotNone(cornice['parent'])
            self.assertEqual(cornice['parent']['type'], 'PHerc')
        # Every pezzo's parent is either a Cornice (nested) or the PHerc (direct)
        for pezzo in result['pezzi']:
            self.assertIsNotNone(pezzo['parent'])
            self.assertIn(pezzo['parent']['type'], ('Cornice', 'PHerc'))
        print(f"[list_cornici_and_pezzi_for_pherc '238'] "
              f"{len(result['cornici'])} cornici, {len(result['pezzi'])} pezzi; "
              f"pezzo parents: {[(p['displayName'], p['parent']['type'], p['parent']['displayName']) for p in result['pezzi']]}")

    def test_list_cornici_and_pezzi_for_pherc_not_found(self):
        self.assertIsNone(self.query_runner.list_cornici_and_pezzi_for_pherc("nonexistent_pherc"))

    def test_find_datasets_for_educelabid(self):
        uuid = self._a_uuid_under_1044()

        datasets = self.query_runner.find_datasets_for_educelabid(uuid)
        self.assertIsInstance(datasets, list)
        self.assertTrue(len(datasets) > 0)
        for ds in datasets:
            self.assertIn('type', ds)
            self.assertIn(ds['type'], ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw'])
        print(f"Found {len(datasets)} datasets for UUID {uuid}")

    def test_find_datasets_for_educelabid_with_predecessors(self):
        uuid = self._a_uuid_under_1044()

        datasets = self.query_runner.find_datasets_for_educelabid_with_predecessors(uuid)
        self.assertIsInstance(datasets, list)
        for ds in datasets:
            self.assertIn('type', ds)
            # each dataset is tagged with the UUID it actually belongs to
            self.assertIn('belongs_to_uuid', ds)
        print(f"Found {len(datasets)} datasets (chain-pooled) for UUID {uuid}")

    def test_find_datasets_for_educelabid_not_found(self):
        datasets = self.query_runner.find_datasets_for_educelabid("nonexistent-uuid")
        self.assertIsInstance(datasets, list)
        self.assertEqual(len(datasets), 0)

    def test_find_all_datasets_for_pherc(self):
        results = self.query_runner.find_all_datasets_for_pherc("1044")
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        for artifact in results:
            self.assertIn('uuid', artifact)
            self.assertIn('artifact_name', artifact)
            self.assertIn('pherc', artifact)
            self.assertIn('cornice', artifact)
            self.assertIn('pezzo', artifact)
            self.assertIn('datasets', artifact)
            self.assertIsInstance(artifact['datasets'], list)
            self.assertEqual(artifact['pherc'], '1044')
            for ds in artifact['datasets']:
                self.assertIn('type', ds)
                self.assertIn('belongs_to_uuid', ds)
        print(f"Found {len(results)} artifacts with datasets for PHerc 1044")

    def test_find_all_datasets_for_pherc_with_type_filter(self):
        results = self.query_runner.find_all_datasets_for_pherc("1044", ds_type=hercdb.DatasetType.PGSRaw)
        self.assertIsInstance(results, list)
        for artifact in results:
            for ds in artifact['datasets']:
                self.assertEqual(ds['type'], 'PGSRaw')
        print(f"Found {len(results)} artifacts with PGSRaw datasets for PHerc 1044")

    def test_find_all_datasets_for_pherc_newest_completed(self):
        results = self.query_runner.find_all_datasets_for_pherc("1044", newest_completed=True)
        self.assertIsInstance(results, list)
        # Each artifact should have at most one dataset per type
        for artifact in results:
            types_seen = [ds['type'] for ds in artifact['datasets']]
            self.assertEqual(len(types_seen), len(set(types_seen)),
                             f"Duplicate types in newest_completed for {artifact['artifact_name']}")
        print(f"Found {len(results)} artifacts with newest completed datasets for PHerc 1044")

    def test_find_all_datasets_for_pherc_not_found(self):
        results = self.query_runner.find_all_datasets_for_pherc("nonexistent_pherc")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

    def test_get_pipeline_status(self):
        result = self.query_runner.get_pipeline_status(STATUS_PIPELINE_ID)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), len(_STATUS_PROCS))
        for p in result:
            self.assertIn('start_time', p)
            self.assertIn('end_time', p)
            self.assertIn('stage', p)
            self.assertIn('status', p)
            self.assertIn('slurm_id', p)
        print(f"[get_pipeline_status '{STATUS_PIPELINE_ID}'] Found {len(result)} stage(s): {result}")

    def test_get_pipeline_status_three_stages_completed(self):
        result = self.query_runner.get_pipeline_status(THREE_STAGE_PIPELINE_ID)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        stages = [p['stage'] for p in result]
        self.assertIn('PGS', stages)
        self.assertIn('SPEC', stages)
        self.assertIn('REG', stages)
        self.assertNotIn('WEB', stages)
        for p in result:
            self.assertEqual(p['status'], 'completed')
            self.assertIn('start_time', p)
            self.assertIsNotNone(p['end_time'], f"end_time should be set for completed stage {p['stage']}")
        print(f"[get_pipeline_status '{THREE_STAGE_PIPELINE_ID}'] Found {len(result)} stage(s): {result}")

    def test_get_all_pipeline_summaries(self):
        result = self.query_runner.get_all_pipeline_summaries()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        # Check structure of each summary
        for summary in result:
            self.assertIn('start_time', summary)
            self.assertIn('dataset_name', summary)
            self.assertIn('artifact_uuid', summary)
            self.assertIn('pipeline_id', summary)
            self.assertIn('status', summary)
            # Status should be one of the expected values
            self.assertIn(summary['status'], [
                'completed', 'partially_completed', 'running', 'failed', 'unknown(error)'
            ])
        print(f"[get_all_pipeline_summaries] Found {len(result)} pipeline(s):")
        for s in result:
            print(f"  {s['pipeline_id']}: {s['dataset_name']} - {s['status']}")


class TestComputePipelineStatus(unittest.TestCase):
    """Unit tests for _compute_pipeline_status helper method."""

    def test_empty_processes_returns_unknown(self):
        status = hercdb.GraphDBConnection._compute_pipeline_status([])
        self.assertEqual(status, 'unknown(error)')

    def test_all_stages_completed(self):
        processes = [
            {'stage': 'PGS', 'status': 'completed'},
            {'stage': 'SPEC', 'status': 'completed'},
            {'stage': 'REG', 'status': 'completed'},
            {'stage': 'WEB', 'status': 'completed'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'completed')

    def test_three_stages_all_completed(self):
        processes = [
            {'stage': 'PGS', 'status': 'completed'},
            {'stage': 'SPEC', 'status': 'completed'},
            {'stage': 'REG', 'status': 'completed'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'completed')

    def test_some_completed_some_still_running(self):
        processes = [
            {'stage': 'PGS', 'status': 'completed'},
            {'stage': 'SPEC', 'status': 'submitted'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'running')

    def test_partially_completed_with_failure(self):
        processes = [
            {'stage': 'SPEC', 'status': 'completed'},
            {'stage': 'REG', 'status': 'failed'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'partially_completed')

    def test_all_stages_failed(self):
        processes = [
            {'stage': 'PGS', 'status': 'failed'},
            {'stage': 'SPEC', 'status': 'failed'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'failed')

    def test_running_status(self):
        processes = [
            {'stage': 'PGS', 'status': 'submitted'},
            {'stage': 'SPEC', 'status': 'submitted'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'running')


class TestFormatDatasetName(unittest.TestCase):
    """Unit tests for _format_dataset_name helper method."""

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()

    def test_full_artifact_info(self):
        artifact_info = {'pherc': '421', 'cornice': 'A', 'pezzo': '1'}
        result = self.db._format_dataset_name(artifact_info)
        self.assertEqual(result, 'PHerc421 Cornice A Pezzo 1')

    def test_pherc_and_cornice_only(self):
        artifact_info = {'pherc': '421', 'cornice': 'A', 'pezzo': None}
        result = self.db._format_dataset_name(artifact_info)
        self.assertEqual(result, 'PHerc421 Cornice A')

    def test_pherc_only(self):
        artifact_info = {'pherc': '421', 'cornice': None, 'pezzo': None}
        result = self.db._format_dataset_name(artifact_info)
        self.assertEqual(result, 'PHerc421')

    def test_empty_artifact_info(self):
        result = self.db._format_dataset_name({})
        self.assertEqual(result, '')

    def test_none_artifact_info(self):
        result = self.db._format_dataset_name(None)
        self.assertEqual(result, '')


if __name__ == "__main__":
    unittest.main()
