"""A shared tray's uuid-sheet names stay on the tray (#61).

The loader test builds its own two papyri on one tray and removes them
afterwards; the graph check is read-only. Requires a live Neo4j connection
(dev, never prod).
"""
import unittest

from educelab import hercdb
from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader, names_papyrus, same_number

PHERCS = ("TEST-61 A", "TEST-61 B")
TRAY = "00000000-0000-4000-8000-000000000061"


class TestSharedTrayNames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.loader = PhercGraphDatabaseLoader()

    @classmethod
    def tearDownClass(cls):
        cls.loader._run_query("""
            MATCH (n) WHERE n.displayName IN $phercs OR n.uuid = $uuid
            OPTIONAL MATCH (n)-[:HAS]->(c)
            DETACH DELETE n, c
            """, phercs=list(PHERCS), uuid=TRAY)
        cls.loader.close()

    def setUp(self):
        # A on its cornice 2, B on its cornice 1: one tray, as 1157 and 1191.
        self.loader._run_query("""
            MERGE (e:EduceLabID {uuid: $uuid})
            WITH e
            UNWIND [[$a, '2 (Osloense)'], [$b, '1 (Osloense)']] AS pc
            MERGE (p:PHerc {displayName: pc[0]})
            MERGE (p)-[:HAS]->(c:Cornice {displayName: pc[1]})
            MERGE (e)-[:ASSIGNED_TO]->(c)
            """, uuid=TRAY, a=PHERCS[0], b=PHERCS[1])

    def node(self, pherc):
        records, _, _ = self.loader._run_query("""
            MATCH (p:PHerc {displayName: $pherc})-[:HAS]->(c:Cornice)
            RETURN p.aliases AS p_aliases, c.aliases AS c_aliases
            """, pherc=pherc)
        return records[0]

    def test_sheet_names_go_on_the_tray(self):
        self.loader.set_alias_on_assigned_node(TRAY, "TEST-61 A-B", "2 (oslo)")
        records, _, _ = self.loader._run_query(
            "MATCH (e:EduceLabID {uuid: $u}) RETURN e.sheet_pherc AS p, e.sheet_cornice AS c", u=TRAY)
        self.assertEqual((records[0]['p'], records[0]['c']), ("TEST-61 A-B", "2 (oslo)"))
        a, b = self.node(PHERCS[0]), self.node(PHERCS[1])
        self.assertIn("2 (oslo)", a['c_aliases'] or [])  # A's own cornice 2
        self.assertNotIn("2 (oslo)", b['c_aliases'] or [])  # not B's cornice 1
        for p in (a, b):
            self.assertNotIn("TEST-61 A-B", p['p_aliases'] or [])

    def test_graph_has_no_shared_tray_names_on_nodes(self):
        records, _, _ = self.loader._run_query("""
            MATCH (e:EduceLabID)-[:ASSIGNED_TO]->(n)
            WITH e, collect(n) AS ns WHERE size(ns) > 1
            UNWIND ns AS n
            OPTIONAL MATCH (n)<-[:HAS*0..2]-(p:PHerc)
            RETURN e.uuid AS uuid, labels(n) AS labels, n.displayName AS n_dn, n.aliases AS n_aliases,
                   p.displayName AS p_dn, p.aliases AS p_aliases
            """)
        trays = {}
        for r in records:
            if r['uuid'] == TRAY:
                continue
            trays.setdefault(r['uuid'], []).append(r)
            if 'PHerc' not in r['labels']:
                with self.subTest(uuid=r['uuid'], node=r['n_dn']):
                    self.assertEqual([a for a in r['n_aliases'] or [] if not same_number(a, r['n_dn'])], [])
        for uuid, rows in trays.items():
            phercs = {r['p_dn']: set(r['p_aliases'] or []) for r in rows if r['p_dn']}
            if len(phercs) < 2:
                continue
            common = set.intersection(*phercs.values())
            for dn in phercs:
                with self.subTest(uuid=uuid, pherc=dn):
                    self.assertEqual({a for a in common if not names_papyrus(a, dn)}, set())


if __name__ == "__main__":
    unittest.main()
