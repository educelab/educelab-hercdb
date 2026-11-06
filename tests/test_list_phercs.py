"""list_phercs: papyri only, each with naming's label, label_parts and kind (#79).

Runs on canned query rows, so it needs no Neo4j.

Run: uv run python -m unittest tests.test_list_phercs
"""
import unittest

from educelab.hercdb.db.connection import GraphDBConnection


def row(name):
    return {'displayName': name, 'literary_work': None, 'unrolling_status': None,
            'metas': [], 'cornici_count': 0, 'pezzi_count': 0}


class CannedConnection(GraphDBConnection):
    """Answers list_phercs' one query from canned rows, no driver."""

    def __init__(self, names):
        self.rows = [row(n) for n in names]

    def _run_query(self, query, **params):
        return self.rows, None, None


NAMES = ['1044', 'Cass. 78 s.n. C', 'cass.75 s. n. B', 'Joannowsky Papyrus',
         # Drawer placeholders.
         'Cassetto', 'frammenti', 'tavoletta',
         # Loose material (Assumption Q-19).
         'folded sheet', 'frammento di papiro ercolanese', 's.n. frammenti 1-2']


class TestListPhercs(unittest.TestCase):

    def setUp(self):
        self.rows = CannedConnection(NAMES).list_phercs()
        self.by_name = {r['displayName']: r for r in self.rows}

    def test_only_papyri(self):
        self.assertEqual(list(self.by_name),
                         ['1044', 'Cass. 78 s.n. C', 'cass.75 s. n. B', 'Joannowsky Papyrus'])
        self.assertEqual({r['kind'] for r in self.rows}, {'papyrus'})

    def test_labels(self):
        self.assertEqual(
            {n: (r['label'], r['label_parts']) for n, r in self.by_name.items()},
            {'1044': ('PHerc. 1044', ['PHerc. 1044']),
             'Cass. 78 s.n. C': ('Cassetto 78 s.n. C', ['Cassetto 78 s.n. C']),
             'cass.75 s. n. B': ('Cassetto 75 s.n. B', ['Cassetto 75 s.n. B']),
             'Joannowsky Papyrus': ('Joannowsky Papyrus', ['Joannowsky Papyrus'])})

    def test_row_fields(self):
        self.assertEqual(list(self.rows[0]), [
            'displayName', 'label', 'label_parts', 'kind', 'literary_work',
            'unrolling_status', 'metadata', 'cornici_count', 'pezzi_count'])

    def test_no_rows(self):
        self.assertEqual(CannedConnection([]).list_phercs(), [])


if __name__ == '__main__':
    unittest.main()
