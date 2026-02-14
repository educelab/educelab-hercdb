import unittest
from educelab import hercdb

class TestPhercDbQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.query_runner = hercdb.connect()
        cls.query_runner.verify_connection()

    def test_find_pherc_by_uuid(self):
        records, summary, keys = self.query_runner.find_pherc_by_uuid("d65a2db0-ffec-5c15-8d3e-b28cf9326a32")
        self.assertTrue(len(records) > 0)
        display_names = [record.data()['ph']['displayName'] for record in records]
        print(display_names)

    def test_find_artifact_name_by_uuid(self):
        result = self.query_runner.find_artifact_name_by_uuid("d65a2db0-ffec-5c15-8d3e-b28cf9326a32")
        self.assertIsNotNone(result)
        self.assertIn('pherc', result)
        self.assertIsNotNone(result['pherc'])
        print(result)

    def test_find_pherc_by_display_name(self):
        records, summary, keys = self.query_runner.find_pherc_by_display_name("421")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertIn("421", display_names)

    def test_find_pherc_by_custodial_institution(self):
        pass

    def test_find_pherc_by_language(self):
        records, summary, keys = self.query_runner.find_pherc_by_language("grc?")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertIn("636", display_names)
        print(display_names)

    def test_find_unrolled_phercs(self):
        records, summary, keys = self.query_runner.find_pherc_by_property_value("unrolling_status", "Partially unrolled")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertTrue(len(display_names) > 0)
        print(display_names)

    def test_find_pherc_by_scorze_value(self):
        records, summary, keys = self.query_runner.find_pherc_by_property_value("scorze", "yes")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertTrue(len(display_names) > 0)
        print(display_names)

    def test_find_unroll_attempted_phercs(self):
        records, summary, keys = self.query_runner.find_pherc_by_property_value("unrolling_status", "Unrolling Attempted")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertTrue(len(display_names) > 0)
        print(display_names)
    
    def test_find_pherc_by_unroller_name(self):
        records, summary, keys = self.query_runner.find_pherc_by_unroller_name("H. Davy")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertTrue(len(display_names) > 0)
        print(display_names)

    def test_find_pherc_by_unrolled_date(self):
        records, summary, keys = self.query_runner.find_pherc_by_property_value("unrolled_date", "1863")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertTrue(len(display_names) > 0)
        print(display_names)
    
    def test_find_pherc_by_literary_work(self):
        records, summary, keys = self.query_runner.find_pherc_by_property_value("literary_work", "Echelaus")
        display_names = [record.data()['ph']['displayName'] for record in records]
        self.assertTrue(len(display_names) > 0)
        print(display_names)

    def test_find_newest_dataset(self):
        records, summary, keys = self.query_runner.find_datasets(hercdb.PGSRawType, "1044", cornice="6", newest_completed=False, properties_only=False)
        self.assertTrue(len(records) > 0)
        #print([record.data() for record in records])
        
        properties = []
        for record in records:
            dataset = record[0]
            properties.append(dict(dataset))
        print("******* properties ******** \n", properties)
    
    def test_find_newest_dataset_properties_only(self):
        properties = self.query_runner.find_datasets(hercdb.PGSRawType, "1044", cornice="6", newest_completed=False, properties_only=True)
        self.assertTrue(len(properties) > 0)
        
        print("******* properties ******** \n", properties)
    
    def test_list_cornici_and_pezzi_for_pherc(self):
        records = self.query_runner.list_cornici_and_pezzi_for_pherc("238")
        self.assertTrue(len(records) > 0)
        #print([record.data() for record in records])
        for record in records:
            print(record.data())
        
        cornici = records[0].data()['cr']
        pezzi = records[0].data()['pz']
        print("Cornici:", cornici)
        print("Pezzi:", pezzi)

    def test_find_educelabids_for_pherc(self):
        results = self.query_runner.find_educelabids_for_pherc("1044")
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        for entry in results:
            self.assertIn('uuid', entry)
            self.assertIn('pherc', entry)
            self.assertIn('cornice', entry)
            self.assertIn('pezzo', entry)
            self.assertIn('artifact_name', entry)
            self.assertEqual(entry['pherc'], '1044')
        print(f"Found {len(results)} EduceLabIDs for PHerc 1044:")
        for entry in results:
            print(f"  {entry['artifact_name']} ({entry['uuid']})")

    def test_find_educelabids_for_pherc_not_found(self):
        results = self.query_runner.find_educelabids_for_pherc("nonexistent_pherc")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)

    def test_find_datasets_for_educelabid(self):
        # First get a UUID from a known PHerc
        educelabids = self.query_runner.find_educelabids_for_pherc("1044")
        self.assertTrue(len(educelabids) > 0, "Need at least one EduceLabID to test")
        uuid = educelabids[0]['uuid']

        datasets = self.query_runner.find_datasets_for_educelabid(uuid)
        self.assertIsInstance(datasets, list)
        self.assertTrue(len(datasets) > 0)
        for ds in datasets:
            self.assertIn('type', ds)
            self.assertIn(ds['type'], ['FlatbedScanDataset', 'PGSRaw', 'SpectralRaw'])
        print(f"Found {len(datasets)} datasets for UUID {uuid}")

    def test_find_datasets_for_educelabid_with_type_filter(self):
        educelabids = self.query_runner.find_educelabids_for_pherc("1044")
        self.assertTrue(len(educelabids) > 0)
        uuid = educelabids[0]['uuid']

        datasets = self.query_runner.find_datasets_for_educelabid(uuid, ds_type=hercdb.PGSRawType)
        self.assertIsInstance(datasets, list)
        for ds in datasets:
            self.assertEqual(ds['type'], 'PGSRaw')
        print(f"Found {len(datasets)} PGSRaw datasets for UUID {uuid}")

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
        print(f"Found {len(results)} artifacts with datasets for PHerc 1044")

    def test_find_all_datasets_for_pherc_with_type_filter(self):
        results = self.query_runner.find_all_datasets_for_pherc("1044", ds_type=hercdb.PGSRawType)
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
        result = self.query_runner.get_pipeline_status("20251222-389")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        print(result)

    def test_get_all_pipeline_summaries(self):
        result = self.query_runner.get_all_pipeline_summaries()
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        # Check structure of each summary
        for summary in result:
            self.assertIn('datetime', summary)
            self.assertIn('dataset_name', summary)
            self.assertIn('artifact_uuid', summary)
            self.assertIn('pipeline_id', summary)
            self.assertIn('status', summary)
            # Status should be one of the expected values
            self.assertIn(summary['status'], [
                'completed', 'partially_completed', 'submitted', 'failed', 'unknown(error)'
            ])
        print(result)


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

    def test_first_stage_completed_partially_completed(self):
        processes = [
            {'stage': 'PGS', 'status': 'completed'},
            {'stage': 'SPEC', 'status': 'submitted'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'partially_completed')

    def test_spec_completed_partially_completed(self):
        processes = [
            {'stage': 'SPEC', 'status': 'completed'},
            {'stage': 'REG', 'status': 'submitted'},
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

    def test_submitted_status(self):
        processes = [
            {'stage': 'PGS', 'status': 'submitted'},
            {'stage': 'SPEC', 'status': 'submitted'},
        ]
        status = hercdb.GraphDBConnection._compute_pipeline_status(processes)
        self.assertEqual(status, 'submitted')


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
