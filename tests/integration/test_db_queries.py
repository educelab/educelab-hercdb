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
            # Processed outputs surface here too as of 0.3.4, so the set is the
            # full DatasetType range, not just the raw labels.
            self.assertIn(ds['type'], {t.value for t in hercdb.DatasetType})
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


class TestProcessedDatasets(unittest.TestCase):
    """Pipeline outputs surface through the dataset queries.

    Self-seeds a REG pipeline (Registered output) and an unfinished WEB one
    against a real EduceLabID, so the assertions don't wait on REG/WEB stages
    actually running in production.
    """

    PIPELINE_ID = f"TEST-PROCESSED-{_TS}"
    WIP_PIPELINE_ID = f"TEST-PROCESSED-WIP-{_TS}"
    REG_PATH = f"/test/registered/{_TS}"
    WEB_PATH = f"/test/webprocessed/{_TS}"

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        artifacts = cls.db.find_all_datasets_for_pherc("1044")
        assert artifacts, "Need at least one UUID under 1044 to test"
        cls.uuid = artifacts[0]['uuid']

        # A completed REG stage -> Registered output.
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            MERGE (p:Pipeline {pipeline_id: $pid})
            MERGE (p)-[:FOR]->(e)
            CREATE (proc:Process {stage: 'REG', status: 'completed', slurm_id: '900201',
                                  start_time: '2026-06-01T10:00:00',
                                  end_time: '2026-06-01T10:30:00'})
            CREATE (proc)-[:STAGE_OF]->(p)
            CREATE (out:Registered {path: $path})
            CREATE (proc)-[:OUTPUT]->(out)
            """, uuid=cls.uuid, pid=cls.PIPELINE_ID, path=cls.REG_PATH)

        # A still-running WEB stage, so `complete` has a False case to prove.
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            MERGE (p:Pipeline {pipeline_id: $pid})
            MERGE (p)-[:FOR]->(e)
            CREATE (proc:Process {stage: 'WEB', status: 'submitted', slurm_id: '900202',
                                  start_time: '2026-06-01T11:00:00'})
            CREATE (proc)-[:STAGE_OF]->(p)
            CREATE (out:WebProcessed {path: $path})
            CREATE (proc)-[:OUTPUT]->(out)
            """, uuid=cls.uuid, pid=cls.WIP_PIPELINE_ID, path=cls.WEB_PATH)

    @classmethod
    def tearDownClass(cls):
        for pid in (cls.PIPELINE_ID, cls.WIP_PIPELINE_ID):
            cls.db._run_query("""
                MATCH (p:Pipeline {pipeline_id: $pid})
                OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
                OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
                DETACH DELETE out, proc, p
                """, pid=pid)

    def _one(self, datasets, path):
        matches = [d for d in datasets if d.get('path') == path]
        self.assertEqual(len(matches), 1, f"expected exactly one row for {path}")
        return matches[0]

    def test_registered_output_is_returned_with_process_fields(self):
        datasets = self.db.find_datasets_for_educelabid_with_predecessors(self.uuid)
        reg = self._one(datasets, self.REG_PATH)
        self.assertEqual(reg['type'], 'Registered')
        self.assertEqual(reg['status'], 'completed')
        self.assertEqual(reg['pipeline_id'], self.PIPELINE_ID)
        self.assertEqual(reg['date_end'], '2026-06-01T10:30:00')
        # `complete` mirrors normalize_complete's string form, so a consumer can
        # gate raw and processed datasets on the same field.
        self.assertEqual(reg['complete'], 'True')
        self.assertIsInstance(reg['complete'], str)

    def test_unfinished_process_is_not_complete(self):
        datasets = self.db.find_datasets_for_educelabid_with_predecessors(self.uuid)
        web = self._one(datasets, self.WEB_PATH)
        self.assertEqual(web['type'], 'WebProcessed')
        self.assertEqual(web['status'], 'submitted')
        self.assertEqual(web['complete'], 'False')

    def test_dataset_type_filter_selects_processed_label(self):
        datasets = self.db.find_datasets_for_educelabid_with_predecessors(
            self.uuid, ds_type=hercdb.DatasetType.Registered)
        self.assertTrue(datasets, "Registered filter should match the seeded output")
        self.assertEqual({d['type'] for d in datasets}, {'Registered'})

    def test_newest_completed_drops_the_unfinished_process(self):
        datasets = self.db.find_datasets_for_educelabid_with_predecessors(
            self.uuid, newest_completed=True)
        paths = {d.get('path') for d in datasets}
        self.assertIn(self.REG_PATH, paths)
        self.assertNotIn(self.WEB_PATH, paths)

    def test_raw_datasets_keep_their_own_complete_flag(self):
        """Regression: processed enrichment must not touch raw rows."""
        raw = self.db.find_datasets_for_educelabid_with_predecessors(
            self.uuid, ds_type=hercdb.DatasetType.PGSRaw)
        for d in raw:
            self.assertNotIn('pipeline_id', d)
            self.assertNotIn('status', d)
            if 'complete' in d:
                self.assertIn(d['complete'], ('True', 'False', 'unknown'))


class TestCrossPipelineProcessInputs(unittest.TestCase):
    """REG/WEB stages whose inputs came from a *different* pipeline.

    A registration- or webify-only submission mints a fresh uber_job_id whose
    only Process is REG (or WEB); the PGSProcessed/SpectralProcessed/Registered
    inputs were produced by an earlier pipeline. `initialize_process` must still
    find them, or the caller is left with a Pipeline node holding zero Processes.
    """

    UPSTREAM_ID = f"TEST-XPIPE-UP-{_TS}"
    REG_ONLY_ID = f"TEST-XPIPE-REG-{_TS}"
    WEB_ONLY_ID = f"TEST-XPIPE-WEB-{_TS}"
    PGS_PATH = f"/test/xpipe/pgsprocessed/{_TS}"
    SPEC_PATH = f"/test/xpipe/spectralprocessed/{_TS}"
    REG_PATH = f"/test/xpipe/registered/{_TS}"
    WEB_PATH = f"/test/xpipe/webprocessed/{_TS}"

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        artifacts = cls.db.find_all_datasets_for_pherc("1044")
        assert artifacts, "Need at least one UUID under 1044 to test"
        cls.uuid = artifacts[0]['uuid']

        # The upstream pipeline that actually produced the REG inputs.
        cls.db._run_query("""
            MATCH (e:EduceLabID {uuid: $uuid})
            MERGE (p:Pipeline {pipeline_id: $pid})
            MERGE (p)-[:FOR]->(e)
            CREATE (pgs:Process {stage: 'PGS', status: 'completed', slurm_id: '900301',
                                 start_time: '2026-07-01T10:00:00',
                                 end_time: '2026-07-01T10:30:00'})
            CREATE (pgs)-[:STAGE_OF]->(p)
            CREATE (pgs)-[:OUTPUT]->(:PGSProcessed {path: $pgs_path})
            CREATE (spec:Process {stage: 'SPEC', status: 'completed', slurm_id: '900302',
                                  start_time: '2026-07-01T11:00:00',
                                  end_time: '2026-07-01T11:30:00'})
            CREATE (spec)-[:STAGE_OF]->(p)
            CREATE (spec)-[:OUTPUT]->(:SpectralProcessed {path: $spec_path})
            """, uuid=cls.uuid, pid=cls.UPSTREAM_ID,
            pgs_path=cls.PGS_PATH, spec_path=cls.SPEC_PATH)

        # The registration-only pipeline: a Pipeline with no Processes of its own.
        cls.db.initialize_pipeline(cls.REG_ONLY_ID, cls.uuid, '2026-07-02T09:00:00')
        cls.db.initialize_pipeline(cls.WEB_ONLY_ID, cls.uuid, '2026-07-03T09:00:00')

    @classmethod
    def tearDownClass(cls):
        for pid in (cls.UPSTREAM_ID, cls.REG_ONLY_ID, cls.WEB_ONLY_ID):
            cls.db._run_query("""
                MATCH (p:Pipeline {pipeline_id: $pid})
                OPTIONAL MATCH (p)<-[:STAGE_OF]-(proc:Process)
                OPTIONAL MATCH (proc)-[:OUTPUT]->(out)
                DETACH DELETE out, proc, p
                """, pid=pid)

    def test_reg_matches_inputs_from_another_pipeline(self):
        proc = self.db.initialize_process(
            self.REG_ONLY_ID, 'REG', [self.PGS_PATH, self.SPEC_PATH],
            self.REG_PATH, '900303', '2026-07-02T09:01:00')
        self.assertIsNotNone(proc, "REG-only submission must record a Process")
        self.assertEqual(proc['stage'], 'REG')

        stages = self.db.get_pipeline_status(self.REG_ONLY_ID)
        self.assertEqual([s['stage'] for s in stages], ['REG'])
        self.assertEqual(sorted(stages[0]['input_dataset_paths']),
                         sorted([self.PGS_PATH, self.SPEC_PATH]))
        self.assertEqual(stages[0]['output_dataset_path'], self.REG_PATH)

    def test_web_matches_registered_from_another_pipeline(self):
        # Depends on the Registered node the REG-only test created.
        self.db.initialize_process(
            self.REG_ONLY_ID, 'REG', [self.PGS_PATH, self.SPEC_PATH],
            self.REG_PATH, '900303', '2026-07-02T09:01:00')

        proc = self.db.initialize_process(
            self.WEB_ONLY_ID, 'WEB', [self.REG_PATH],
            self.WEB_PATH, '900304', '2026-07-03T09:01:00')
        self.assertIsNotNone(proc, "WEB-only submission must record a Process")
        self.assertEqual(proc['stage'], 'WEB')

        stages = self.db.get_pipeline_status(self.WEB_ONLY_ID)
        self.assertEqual([s['stage'] for s in stages], ['WEB'])
        self.assertEqual(stages[0]['input_dataset_paths'], [self.REG_PATH])

    def test_missing_input_still_returns_none(self):
        """The relaxed MATCH must not start recording processes with no input."""
        proc = self.db.initialize_process(
            self.REG_ONLY_ID, 'REG', [self.PGS_PATH, '/test/xpipe/does-not-exist'],
            self.REG_PATH, '900305', '2026-07-02T09:02:00')
        self.assertIsNone(proc)


if __name__ == "__main__":
    unittest.main()
