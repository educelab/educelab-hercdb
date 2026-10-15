"""list_phercs: every scroll in one call, agreeing with get_artifact_info (#22).

Read-only. Requires a live Neo4j connection (dev, never prod).
"""
import random
import unittest

from educelab import hercdb

FIELDS = ('literary_work', 'unrolling_status', 'cornici_count', 'pezzi_count')


class TestListPhercs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()
        cls.rows = cls.db.list_phercs()
        cls.by_name = {r['displayName']: r for r in cls.rows}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_every_pherc_but_the_placeholders(self):
        every = {r['display_name'] for r in self.db.list_all_pherc_display_names()}
        placeholders = set(self.db._PHERC_PLACEHOLDERS)
        self.assertTrue(placeholders <= every, "placeholders should exist in the graph")
        self.assertEqual(set(self.by_name), every - placeholders)
        self.assertEqual(len(self.rows), len(self.by_name), "one row per PHerc")

    def test_rows_match_artifact_detail(self):
        with_author = [r['displayName'] for r in self.rows if 'Author' in r['metadata']]
        with_cornici = [r['displayName'] for r in self.rows if r['cornici_count']]
        with_pezzi = [r['displayName'] for r in self.rows if r['pezzi_count']]
        self.assertTrue(with_author and with_cornici and with_pezzi)
        sample = set(random.Random(22).sample(sorted(self.by_name), 30))
        sample |= {with_author[0], with_cornici[0], with_pezzi[0]}
        for name in sorted(sample):
            with self.subTest(pherc=name):
                row, info = self.by_name[name], self.db.get_artifact_info(name)
                self.assertEqual({k: row[k] for k in FIELDS}, {k: info.get(k) for k in FIELDS})
                expected = {k: v for k, v in info['metadata'].items() if k in ('Author', 'Language')}
                self.assertEqual(row['metadata'], expected)


if __name__ == "__main__":
    unittest.main()
