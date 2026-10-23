"""kind / method / label on the artifact views (#23).

/subdivisions, /artifacts?pherc= and /artifacts/{uuid} each add
``naming.describe``'s fields to every node. Read-only. Requires a live Neo4j
connection (dev, never prod).
"""
import unittest

from educelab import hercdb
from educelab.hercdb import naming

FIELDS = ('kind', 'method', 'label', 'label_parts')
CASS_51_A = '6a5d9d82-69b4-5239-92ef-75787e9e8ccb'


class TestObjectKind(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hercdb.config._load_config()
        cls.db = hercdb.connect()
        cls.db.verify_connection()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def subdivisions(self, pherc):
        result = self.db.list_cornici_and_pezzi_for_pherc(pherc)
        self.assertIsNotNone(result, pherc)
        nodes = {n['displayName']: n for n in result['cornici'] + result['pezzi']}
        return result, nodes

    def test_subdivisions_carry_the_fields(self):
        result, nodes = self.subdivisions('465')
        for node in [result['pherc'], *nodes.values()]:
            self.assertTrue(set(FIELDS) <= set(node), node['displayName'])
        self.assertEqual(result['pherc']['kind'], 'papyrus')
        self.assertEqual(nodes['1 (Fackelmann)']['kind'], 'cornice')
        self.assertEqual(nodes['1 (Fackelmann)']['method'], 'Fackelmann')

    def test_nested_pezzo_is_named_under_its_cornice(self):
        _, nodes = self.subdivisions('465')
        pezzo = nodes['465/2']
        self.assertEqual(pezzo['kind'], 'pezzo')
        self.assertEqual(pezzo['method'], 'Fackelmann')
        self.assertEqual(pezzo['label_parts'], ['PHerc. 465', 'Cornice 1 (Fackelmann)', 'Pezzo 465/2'])

    def test_scorza_and_cassetto_piece(self):
        _, nodes = self.subdivisions('90')
        self.assertEqual(nodes['Scorze da 90 a 223']['kind'], 'scorza')
        _, nodes = self.subdivisions('1362')
        self.assertEqual(nodes['Cass.75']['kind'], 'cassetto_piece')
        self.assertEqual(nodes['Cass.75']['label'], 'PHerc. 1362, Cassetto 75')

    def test_placeholder_trays(self):
        result, nodes = self.subdivisions('tavoletta')
        self.assertIsNone(result['pherc']['kind'])
        self.assertEqual({n['kind'] for n in nodes.values()}, {'tavoletta'})
        result, nodes = self.subdivisions('Cassetto')
        self.assertEqual({n['kind'] for n in nodes.values()}, {'whole_cassetto'})  # Assumption Q-09

    def test_artifact_detail_by_name(self):
        info = self.db.get_artifact_info('465', '1 (Fackelmann)', '465/2')
        self.assertEqual(info['kind'], 'pezzo')
        self.assertEqual(info['label'], 'PHerc. 465, Cornice 1 (Fackelmann), Pezzo 465/2')
        self.assertEqual(self.db.get_artifact_info('90')['kind'], 'papyrus')

    def test_artifact_by_uuid(self):
        location = self.db.find_artifact_location_by_uuid(CASS_51_A)
        self.assertEqual(location['kind'], 'whole_cassetto')
        self.assertEqual(location['label'], 'Cassetto 51 (A)')  # Assumption Q-10

    def test_tray_on_every_list_row(self):
        rows = {r['uuid']: r for r in self.db.list_artifacts()}
        self.assertTrue(all(r['tray']['label'] for r in rows.values()))
        shared = rows['02160e53-71b8-52ba-bcd3-faf6c6917c66']['tray']
        self.assertEqual(shared['label'], 'Cornice 1 (Fackelmann): PHerc. 221, 465, 466, 467, 1081')
        self.assertEqual(rows[CASS_51_A]['tray']['kind'], 'whole_cassetto')
        # Placeholder trays are listed: they belong in the tray view.
        kinds = {r['tray']['kind'] for r in rows.values()}
        self.assertTrue({'tavoletta', 'whole_cassetto', 'frammenti'} <= kinds)

    def test_shared_with_other_papyri(self):
        _, nodes = self.subdivisions('465')
        others = {s['pherc'] for s in nodes['465/2']['shared_with']}
        self.assertEqual(others, {'221', '466', '467', '1081'})
        self.assertEqual(nodes['1 (Osloense)']['shared_with'], [])
        # A papyrus sharing a UUID with its own Cass. node (#40) shares nothing.
        result, nodes = self.subdivisions('1362')
        self.assertEqual(result['pherc']['shared_with'], [])
        self.assertEqual(nodes['Cass.75']['shared_with'], [])

    def test_every_assigned_object_gets_a_kind(self):
        # Every row and every artifact on a shared tray. A UUID on a PHerc node
        # (72, 1362, 1363 until #40) reports kind "papyrus".
        for row in self.db.list_artifacts():
            for artifact in [row, *row['artifacts']]:
                with self.subTest(uuid=row['uuid'], artifact=artifact['displayName']):
                    self.assertIn(artifact['kind'], {
                        naming.PAPYRUS, naming.CORNICE, naming.SCORZA, naming.PEZZO,
                        naming.CASSETTO_PIECE, naming.WHOLE_CASSETTO, naming.TAVOLETTA,
                        naming.FRAMMENTI,
                    })


if __name__ == "__main__":
    unittest.main()
