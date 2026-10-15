"""get_pipeline_summaries_page on real data (#26).

Pages stitched together equal the whole sorted list, for every sort, and a
search keeps exactly the pipelines whose fields contain it. Read-only.
Requires a live Neo4j connection (dev, never prod).
"""
import unittest

from educelab import hercdb
from educelab.hercdb.db.connection import PIPELINE_SORTS, _page_pipeline_summaries


class TestPipelinesPaging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        cls.rows = cls.db.get_all_pipeline_summaries()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_pages_cover_everything_once(self):
        for sort in PIPELINE_SORTS:
            for direction in ('asc', 'desc'):
                with self.subTest(sort=sort, dir=direction):
                    whole = _page_pipeline_summaries(self.rows, None, sort, direction, 0, None)
                    stitched, offset = [], 0
                    while True:
                        page = _page_pipeline_summaries(self.rows, None, sort, direction, offset, 1000)
                        if not page['rows']:
                            break
                        stitched += page['rows']
                        offset += 1000
                    self.assertEqual(stitched, whole['rows'])
                    self.assertEqual(len(stitched), len(self.rows))

    def test_search_by_artifact_uuid(self):
        uuid = next(r['artifact_uuid'] for r in self.rows if r['artifact_uuid'])
        page = self.db.get_pipeline_summaries_page(search=uuid, limit=5)
        expected = sum(r['artifact_uuid'] == uuid for r in self.rows)
        self.assertEqual(page['matched'], expected)
        self.assertEqual(page['total'], len(self.rows))
        self.assertTrue(all(r['artifact_uuid'] == uuid for r in page['rows']))
        self.assertLessEqual(len(page['rows']), 5)

    def test_search_by_pipeline_id(self):
        pid = self.rows[len(self.rows) // 2]['pipeline_id']
        page = self.db.get_pipeline_summaries_page(search=pid)
        self.assertIn(pid, [r['pipeline_id'] for r in page['rows']])


if __name__ == "__main__":
    unittest.main()
