"""The loader moves a papyrus-level UUID onto the object that carries it (#40).

Builds its own PHerc / Cornice / EduceLabIDs and removes them afterwards.
Requires a live Neo4j connection (dev, never prod).
"""
import unittest

from educelab import hercdb
from educelab.hercdb.loader.graph_loader import PhercGraphDatabaseLoader

PHERC = "TEST-40 papyrus"
ON_BOTH = "00000000-0000-4000-8000-000000000040"
PHERC_ONLY = "00000000-0000-4000-8000-000000000041"


class TestUnassignPherc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.loader = PhercGraphDatabaseLoader()

    @classmethod
    def tearDownClass(cls):
        cls.loader._run_query("""
            MATCH (n) WHERE n.displayName = $pherc OR n.uuid IN [$a, $b]
            OPTIONAL MATCH (n)-[:HAS]->(c)
            DETACH DELETE n, c
            """, pherc=PHERC, a=ON_BOTH, b=PHERC_ONLY)
        cls.loader.close()

    def setUp(self):
        self.loader._run_query("""
            MERGE (ph:PHerc {displayName: $pherc})
            MERGE (ph)-[:HAS]->(c:Cornice {displayName: 'Cass. 1'})
            MERGE (both:EduceLabID {uuid: $a})
            MERGE (only:EduceLabID {uuid: $b})
            MERGE (both)-[:ASSIGNED_TO]->(ph)
            MERGE (both)-[:ASSIGNED_TO]->(c)
            MERGE (only)-[:ASSIGNED_TO]->(ph)
            """, pherc=PHERC, a=ON_BOTH, b=PHERC_ONLY)

    def assigned(self, uuid):
        records, _, _ = self.loader._run_query("""
            MATCH (:EduceLabID {uuid: $u})-[:ASSIGNED_TO]->(n)
            RETURN labels(n)[0] AS label ORDER BY label
            """, u=uuid)
        return [r['label'] for r in records or []]

    def test_moves_a_uuid_its_object_carries(self):
        self.loader.unassign_pherc_if_child_assigned(ON_BOTH, PHERC)
        self.assertEqual(self.assigned(ON_BOTH), ['Cornice'])

    def test_leaves_a_uuid_on_the_papyrus_alone(self):
        self.loader.unassign_pherc_if_child_assigned(PHERC_ONLY, PHERC)
        self.assertEqual(self.assigned(PHERC_ONLY), ['PHerc'])


if __name__ == "__main__":
    unittest.main()
