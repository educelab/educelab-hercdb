"""Applying the extra scan links (#43).

Builds its own scans and trays and removes them afterwards. Requires a live
Neo4j connection (dev, never prod).
"""
import unittest

from neo4j import GraphDatabase

from educelab import hercdb
from educelab.hercdb import config
from educelab.hercdb.loader import extra_scan_links

SCAN = "00000000-0000-4000-8000-0000000004a1"
EXCLUDED = "00000000-0000-4000-8000-0000000004a2"
TRAY = "00000000-0000-4000-8000-0000000004b1"
OTHER = "00000000-0000-4000-8000-0000000004b2"
ALL = [SCAN, EXCLUDED, TRAY, OTHER]


class TestExtraScanLinks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password))

    @classmethod
    def tearDownClass(cls):
        cls.driver.execute_query("MATCH (n) WHERE n.uuid IN $u DETACH DELETE n", u=ALL, database_='neo4j')
        cls.driver.close()

    def setUp(self):
        self.driver.execute_query("""
            MATCH (n) WHERE n.uuid IN $u DETACH DELETE n
            WITH count(*) AS _
            CREATE (s:SpectralRaw {uuid: $scan})-[:BELONGS_TO]->(:EduceLabID {uuid: $tray})
            CREATE (:SpectralRaw {uuid: $excluded, excluded: true})
            CREATE (:EduceLabID {uuid: $other})
            """, u=ALL, scan=SCAN, tray=TRAY, excluded=EXCLUDED, other=OTHER, database_='neo4j')

    def trays(self, scan):
        records, _, _ = self.driver.execute_query(
            "MATCH (:SpectralRaw {uuid: $s})-[:BELONGS_TO]->(e) RETURN e.uuid AS e ORDER BY e",
            s=scan, database_='neo4j')
        return [r['e'] for r in records]

    def link(self, scan, eid):
        return [{'label': 'SpectralRaw', 'scan_uuid': scan, 'eid': eid}]

    def test_adds_the_second_tray_once(self):
        links = self.link(SCAN, OTHER)
        self.assertEqual(extra_scan_links.apply(self.driver, links), 1)
        extra_scan_links.apply(self.driver, links)  # idempotent
        self.assertEqual(self.trays(SCAN), sorted([TRAY, OTHER]))

    def test_never_relinks_an_excluded_scan(self):
        extra_scan_links.apply(self.driver, self.link(EXCLUDED, OTHER))
        self.assertEqual(self.trays(EXCLUDED), [])

    def test_a_missing_tray_fails_loudly(self):
        with self.assertRaises(SystemExit):
            extra_scan_links.apply(self.driver, self.link(SCAN, "00000000-0000-4000-8000-0000000004ff"))


if __name__ == '__main__':
    unittest.main()
