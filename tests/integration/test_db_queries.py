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

    def test_get_pipeline_status(self):
        result = self.query_runner.get_pipeline_status("20251222-389")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        print(result)


if __name__ == "__main__":
    unittest.main()
